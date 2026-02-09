"""X/Twitter scraper using official XDK."""

import asyncio
from datetime import datetime, timedelta, timezone
from loguru import logger
from requests.exceptions import HTTPError
from xdk import Client

from src.models import Tweet, Account


class XScraper:
    """Scraper for X/Twitter using official API v2 (XDK)."""

    def __init__(
        self,
        bearer_token: str,
        rate_limit_delay: float = 2.0,
        rate_limit_batch_size: int = 10,
        rate_limit_batch_delay: float = 10.0,
    ):
        """Initialize the scraper with API credentials and rate limit settings.

        Args:
            bearer_token: X API v2 bearer token
            rate_limit_delay: Delay between each account request (seconds)
            rate_limit_batch_size: Number of accounts to process before taking a longer break
            rate_limit_batch_delay: Delay between batches (seconds)

        Note:
            When rate limit is hit, the scraper will skip the request and continue
            with the next account instead of retrying.
        """
        self.client = Client(bearer_token=bearer_token)
        self.rate_limit_delay = rate_limit_delay
        self.rate_limit_batch_size = rate_limit_batch_size
        self.rate_limit_batch_delay = rate_limit_batch_delay
        self._request_count = 0

    async def _execute_with_retry(self, func, *args, **kwargs):
        """Execute a function and skip on rate limit errors.

        Args:
            func: The function to execute
            *args, **kwargs: Arguments to pass to the function

        Returns:
            The result of the function call, or None if rate limited
        """
        try:
            self._request_count += 1
            result = func(*args, **kwargs)
            return result
        except HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 429:
                logger.warning(
                    f"⚠️  Rate limit hit! Skipping this request to continue processing. "
                    f"Error: {e}"
                )
                return None
            elif status is not None and status >= 500:
                logger.warning(
                    f"X API server error ({status}): {e}. Skipping this request."
                )
                return None
            else:
                logger.error(f"HTTP error ({status}): {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def get_user_info(self, username: str) -> Account | None:
        """Fetch user information by username."""
        try:
            response = await self._execute_with_retry(
                self.client.users.get_by_username,
                username=username,
                user_fields=["id", "name", "description", "created_at"],
            )
            if not response:
                logger.warning(f"Skipped fetching user info for {username} due to rate limit")
                return None
            data = response.data
            if data:
                return Account(
                    username=username,
                    user_id=str(data['id']),
                    display_name=data.get('name'),
                    description=data.get('description'),
                )
            return None
        except Exception as e:
            logger.error(f"Error fetching user {username}: {e}")
            return None

    async def get_recent_tweets(
        self,
        username: str,
        since: datetime | None = None,
        max_results: int = 100,
        user_id: str | None = None,
        display_name: str | None = None,
    ) -> list[Tweet]:
        """Fetch recent tweets from a user.

        Args:
            username: Twitter username without @
            since: Fetch tweets after this time (default: 24 hours ago)
            max_results: Maximum number of tweets to fetch
            user_id: Cached user ID (skips API lookup if provided)
            display_name: Cached display name

        Returns:
            List of Tweet objects
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=1)

        tweets: list[Tweet] = []

        try:
            # Use cached user_id if available, otherwise fetch from API
            if not user_id:
                user_response = await self._execute_with_retry(
                    self.client.users.get_by_username, username=username
                )
                if not user_response or not user_response.data:
                    if not user_response:
                        logger.warning(f"Skipped fetching user {username} due to rate limit")
                    else:
                        logger.warning(f"User not found: {username}")
                    return tweets

                user_id = user_response.data['id']
                display_name = user_response.data.get('name', username)

                # Small delay between getting user and getting tweets
                await asyncio.sleep(1)

            # Fetch tweets - format time as RFC3339 (X API requirement)
            start_time_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Get user tweets (using XDK's users.get_posts - returns a generator)
            posts_iter = await self._execute_with_retry(
                self.client.users.get_posts,
                id=user_id,
                start_time=start_time_str,
                max_results=min(max_results, 100),
                tweet_fields=[
                    "created_at",
                    "public_metrics",
                    "referenced_tweets",
                    "attachments",
                ],
                expansions=["attachments.media_keys"],
                media_fields=["url", "preview_image_url"],
            )

            if not posts_iter:
                logger.warning(f"Skipped fetching tweets from {username} due to rate limit")
                return tweets

            # Get first page from generator
            try:
                response = next(posts_iter, None)
            except StopIteration:
                response = None
            
            if not response or not response.data:
                logger.info(f"No recent tweets from {username}")
                return tweets

            # Process media
            media_map = {}
            includes = getattr(response, "includes", None)
            if includes and isinstance(includes, dict):
                media_list = includes.get("media", [])
                for media in media_list:
                    if isinstance(media, dict):
                        media_key = media.get("media_key")
                        media_url = media.get("url") or media.get("preview_image_url")
                        if media_key and media_url:
                            media_map[media_key] = media_url

            for tweet in response.data:
                # XDK returns tweets as dicts
                if not isinstance(tweet, dict):
                    continue
                
                # Check if retweet or reply
                is_retweet = False
                is_reply = False
                referenced_tweets = tweet.get("referenced_tweets", [])
                if referenced_tweets:
                    for ref in referenced_tweets:
                        ref_type = ref.get("type") if isinstance(ref, dict) else getattr(ref, "type", None)
                        if ref_type == "retweeted":
                            is_retweet = True
                        elif ref_type == "replied_to":
                            is_reply = True

                # Get media URLs
                media_urls = []
                attachments = tweet.get("attachments")
                if attachments and isinstance(attachments, dict):
                    media_keys = attachments.get("media_keys", [])
                    for key in media_keys:
                        if key in media_map:
                            media_urls.append(media_map[key])

                metrics = tweet.get("public_metrics", {})

                # Parse created_at if it's a string
                created_at = tweet.get("created_at")
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                elif created_at is None:
                    created_at = datetime.now(timezone.utc)

                tweets.append(
                    Tweet(
                        tweet_id=str(tweet.get("id")),
                        author_username=username,
                        author_display_name=display_name,
                        content=tweet.get("text", ""),
                        created_at=created_at,
                        likes=metrics.get("like_count", 0) if metrics else 0,
                        retweets=metrics.get("retweet_count", 0) if metrics else 0,
                        replies=metrics.get("reply_count", 0) if metrics else 0,
                        views=metrics.get("impression_count") if metrics else None,
                        url=f"https://x.com/{username}/status/{tweet.get('id')}",
                        is_retweet=is_retweet,
                        is_reply=is_reply,
                        media_urls=media_urls,
                    )
                )

            logger.info(f"Fetched {len(tweets)} tweets from {username}")

        except Exception as e:
            logger.error(f"Error fetching tweets from {username}: {e}")

        return tweets

    async def get_tweets_for_accounts(
        self,
        accounts: list[Account],
        since_map: dict[str, datetime | None] | None = None,
    ) -> list[Tweet]:
        """Fetch tweets from multiple accounts with rate limiting.

        Uses cached user_id from Account objects to skip API lookups.
        Uses per-account since times for incremental fetching.

        Args:
            accounts: List of accounts to fetch tweets from (with cached user_id)
            since_map: Per-account since times {username: datetime}. Falls back to 24h ago.

        Returns:
            List of all tweets sorted by creation time (newest first)
        """
        all_tweets: list[Tweet] = []
        total_accounts = len(accounts)
        self._request_count = 0
        since_map = since_map or {}

        logger.info(
            f"Starting to fetch tweets from {total_accounts} accounts "
            f"(batch size: {self.rate_limit_batch_size}, "
            f"delay: {self.rate_limit_delay}s, "
            f"batch delay: {self.rate_limit_batch_delay}s)"
        )

        for i, account in enumerate(accounts):
            account_num = i + 1

            # Check if we need a batch delay
            if i > 0 and i % self.rate_limit_batch_size == 0:
                logger.info(
                    f"Completed batch of {self.rate_limit_batch_size} accounts. "
                    f"Taking a {self.rate_limit_batch_delay:.0f}s break to avoid rate limits..."
                )
                await asyncio.sleep(self.rate_limit_batch_delay)

            since = since_map.get(account.username)
            since_label = since.strftime("%m-%d %H:%M") if since else "24h ago"
            logger.info(
                f"[{account_num}/{total_accounts}] Fetching tweets from @{account.username} (since {since_label})..."
            )

            try:
                tweets = await self.get_recent_tweets(
                    account.username,
                    since=since,
                    user_id=account.user_id,
                    display_name=account.display_name,
                )
                all_tweets.extend(tweets)
                logger.info(
                    f"[{account_num}/{total_accounts}] Got {len(tweets)} tweets from @{account.username}"
                )
            except Exception as e:
                logger.error(
                    f"[{account_num}/{total_accounts}] Failed to fetch tweets from @{account.username}: {e}"
                )
                # Continue with next account instead of failing completely

            # Delay before next account (except for the last one)
            if account_num < total_accounts:
                logger.debug(f"Waiting {self.rate_limit_delay}s before next request...")
                await asyncio.sleep(self.rate_limit_delay)

        logger.info(
            f"Completed fetching tweets. Total: {len(all_tweets)} tweets from {total_accounts} accounts. "
            f"API requests made: {self._request_count}"
        )

        # Sort by creation time, newest first
        all_tweets.sort(key=lambda t: t.created_at, reverse=True)
        return all_tweets

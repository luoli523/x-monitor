"""X/Twitter scraper using official API."""

import asyncio
from datetime import datetime, timedelta, timezone
from loguru import logger
import tweepy

from src.models import Tweet, Account


class XScraper:
    """Scraper for X/Twitter using official API v2."""

    def __init__(
        self,
        bearer_token: str,
        rate_limit_delay: float = 5.0,
        rate_limit_batch_size: int = 5,
        rate_limit_batch_delay: float = 60.0,
        rate_limit_max_retries: int = 3,
        rate_limit_retry_base_delay: float = 60.0,
    ):
        """Initialize the scraper with API credentials and rate limit settings.

        Args:
            bearer_token: Twitter API v2 bearer token
            rate_limit_delay: Delay between each account request (seconds)
            rate_limit_batch_size: Number of accounts to process before taking a longer break
            rate_limit_batch_delay: Delay between batches (seconds)
            rate_limit_max_retries: [DEPRECATED] No longer used, kept for compatibility
            rate_limit_retry_base_delay: [DEPRECATED] No longer used, kept for compatibility
        
        Note:
            When rate limit is hit, the scraper will skip the request and continue
            with the next account instead of retrying.
        """
        self.client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
        self.rate_limit_delay = rate_limit_delay
        self.rate_limit_batch_size = rate_limit_batch_size
        self.rate_limit_batch_delay = rate_limit_batch_delay
        self.rate_limit_max_retries = rate_limit_max_retries  # Kept for compatibility
        self.rate_limit_retry_base_delay = rate_limit_retry_base_delay  # Kept for compatibility
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
        except tweepy.TooManyRequests as e:
            logger.warning(
                f"⚠️  Rate limit hit! Skipping this request to continue processing. "
                f"Error: {e}"
            )
            return None
        except tweepy.TwitterServerError as e:
            logger.warning(
                f"Twitter server error: {e}. Skipping this request."
            )
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def get_user_info(self, username: str) -> Account | None:
        """Fetch user information by username."""
        try:
            user = await self._execute_with_retry(
                self.client.get_user,
                username=username,
                user_fields=["id", "name", "description", "created_at"],
            )
            if not user:
                logger.warning(f"Skipped fetching user info for {username} due to rate limit")
                return None
            if user.data:
                return Account(
                    username=username,
                    user_id=str(user.data.id),
                    display_name=user.data.name,
                    description=user.data.description,
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
    ) -> list[Tweet]:
        """Fetch recent tweets from a user.

        Args:
            username: Twitter username without @
            since: Fetch tweets after this time (default: 24 hours ago)
            max_results: Maximum number of tweets to fetch

        Returns:
            List of Tweet objects
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=1)

        tweets: list[Tweet] = []

        try:
            # First get user ID
            user = await self._execute_with_retry(
                self.client.get_user, username=username
            )
            if not user or not user.data:
                if not user:
                    logger.warning(f"Skipped fetching user {username} due to rate limit")
                else:
                    logger.warning(f"User not found: {username}")
                return tweets

            user_id = user.data.id
            display_name = user.data.name

            # Small delay between getting user and getting tweets
            await asyncio.sleep(1)

            # Fetch tweets - format time as RFC3339 (Twitter API requirement)
            start_time_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            response = await self._execute_with_retry(
                self.client.get_users_tweets,
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

            if not response:
                logger.warning(f"Skipped fetching tweets from {username} due to rate limit")
                return tweets

            if not response.data:
                logger.info(f"No recent tweets from {username}")
                return tweets

            # Process media
            media_map = {}
            if response.includes and "media" in response.includes:
                for media in response.includes["media"]:
                    media_map[media.media_key] = getattr(media, "url", None) or getattr(
                        media, "preview_image_url", None
                    )

            for tweet in response.data:
                # Check if retweet or reply
                is_retweet = False
                is_reply = False
                if tweet.referenced_tweets:
                    for ref in tweet.referenced_tweets:
                        if ref.type == "retweeted":
                            is_retweet = True
                        elif ref.type == "replied_to":
                            is_reply = True

                # Get media URLs
                media_urls = []
                if tweet.attachments and "media_keys" in tweet.attachments:
                    for key in tweet.attachments["media_keys"]:
                        if key in media_map and media_map[key]:
                            media_urls.append(media_map[key])

                metrics = tweet.public_metrics or {}

                tweets.append(
                    Tweet(
                        tweet_id=str(tweet.id),
                        author_username=username,
                        author_display_name=display_name,
                        content=tweet.text,
                        created_at=tweet.created_at,
                        likes=metrics.get("like_count", 0),
                        retweets=metrics.get("retweet_count", 0),
                        replies=metrics.get("reply_count", 0),
                        views=metrics.get("impression_count"),
                        url=f"https://x.com/{username}/status/{tweet.id}",
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
        since: datetime | None = None,
    ) -> list[Tweet]:
        """Fetch tweets from multiple accounts with rate limiting.

        This method implements careful rate limiting to avoid hitting Twitter API limits:
        - Delays between each account request
        - Batch processing with longer delays between batches
        - Progress logging for monitoring

        Args:
            accounts: List of accounts to fetch tweets from
            since: Fetch tweets after this time

        Returns:
            List of all tweets sorted by creation time (newest first)
        """
        all_tweets: list[Tweet] = []
        total_accounts = len(accounts)
        self._request_count = 0

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

            logger.info(
                f"[{account_num}/{total_accounts}] Fetching tweets from @{account.username}..."
            )

            try:
                tweets = await self.get_recent_tweets(account.username, since=since)
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

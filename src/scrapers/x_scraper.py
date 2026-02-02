"""X/Twitter scraper using official API."""

from datetime import datetime, timedelta, timezone
from loguru import logger
import tweepy

from src.models import Tweet, Account


class XScraper:
    """Scraper for X/Twitter using official API v2."""

    def __init__(self, bearer_token: str):
        """Initialize the scraper with API credentials."""
        self.client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

    async def get_user_info(self, username: str) -> Account | None:
        """Fetch user information by username."""
        try:
            user = self.client.get_user(
                username=username,
                user_fields=["id", "name", "description", "created_at"],
            )
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
            user = self.client.get_user(username=username)
            if not user.data:
                logger.warning(f"User not found: {username}")
                return tweets

            user_id = user.data.id
            display_name = user.data.name

            # Fetch tweets
            response = self.client.get_users_tweets(
                id=user_id,
                start_time=since.isoformat(),
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
        """Fetch tweets from multiple accounts."""
        all_tweets: list[Tweet] = []

        for account in accounts:
            tweets = await self.get_recent_tweets(account.username, since=since)
            all_tweets.extend(tweets)

        # Sort by creation time, newest first
        all_tweets.sort(key=lambda t: t.created_at, reverse=True)
        return all_tweets

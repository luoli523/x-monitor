"""Main X Monitor Agent that orchestrates all components."""

from datetime import datetime, timedelta, timezone

from loguru import logger

from src.config import Settings
from src.storage import Storage
from src.scrapers import XScraper
from src.analyzers import LLMAnalyzer
from src.notifiers import EmailNotifier, TelegramNotifier
from src.models import Account, DailySummary


class XMonitorAgent:
    """Main agent for monitoring X/Twitter accounts."""

    def __init__(self, settings: Settings):
        """Initialize the agent with settings."""
        self.settings = settings
        self.storage = Storage(settings.database_path)
        self.scraper = XScraper(
            bearer_token=settings.x_bearer_token,
            rate_limit_delay=settings.rate_limit_delay,
            rate_limit_batch_size=settings.rate_limit_batch_size,
            rate_limit_batch_delay=settings.rate_limit_batch_delay,
        )
        self.analyzer = LLMAnalyzer(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_completion_tokens=settings.openai_max_completion_tokens,
            temperature=settings.openai_temperature,
        )

        # Initialize notifiers
        self.notifiers: list[EmailNotifier | TelegramNotifier] = []

        if settings.email_enabled:
            self.notifiers.append(
                EmailNotifier(
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    username=settings.smtp_user,
                    password=settings.smtp_password,
                    to_email=settings.email_to,
                )
            )
            logger.info("Email notifications enabled")

        if settings.telegram_enabled:
            self.notifiers.append(
                TelegramNotifier(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id,
                )
            )
            logger.info("Telegram notifications enabled")

    async def initialize(self) -> None:
        """Initialize storage and other components."""
        await self.storage.initialize()
        logger.info("X Monitor Agent initialized")

    async def add_account(self, username: str) -> Account | None:
        """Add a new account to monitor.

        Fetches user info from API and caches user_id, display_name, description
        so that subsequent runs don't need to call the API for user info.

        Args:
            username: Twitter username without @

        Returns:
            Account if added successfully, None otherwise
        """
        # Clean username
        username = username.lstrip("@").strip()

        # Check if already exists
        existing = await self.storage.get_account(username)
        if existing:
            logger.warning(f"Account @{username} already being monitored")
            return existing

        # Fetch account info from API (includes user_id for caching)
        account = await self.scraper.get_user_info(username)
        if account:
            await self.storage.add_account(account)
            return account

        logger.error(f"Could not find Twitter account: @{username}")
        return None

    async def remove_account(self, username: str) -> bool:
        """Remove an account from monitoring."""
        username = username.lstrip("@").strip()
        return await self.storage.remove_account(username)

    async def list_accounts(self) -> list[Account]:
        """List all monitored accounts."""
        return await self.storage.get_accounts()

    async def _ensure_account_info(self, accounts: list[Account]) -> list[Account]:
        """Ensure all accounts have cached user_id. Fetch from API if missing.

        Returns updated account list with user_id populated.
        """
        updated = []
        for account in accounts:
            if account.user_id:
                updated.append(account)
                continue

            # Need to fetch user info from API
            logger.info(f"Fetching user info for @{account.username} (first time)...")
            info = await self.scraper.get_user_info(account.username)
            if info and info.user_id:
                # Cache to accounts.json
                await self.storage.update_account_info(
                    account.username, info.user_id, info.display_name, info.description
                )
                account.user_id = info.user_id
                account.display_name = info.display_name or account.display_name
                account.description = info.description or account.description
                logger.info(f"Cached user info for @{account.username} (id={info.user_id})")
            else:
                logger.warning(f"Could not fetch user info for @{account.username}, will retry next run")
            updated.append(account)

        cached_count = sum(1 for a in updated if a.user_id)
        logger.info(f"Account info: {cached_count}/{len(updated)} have cached user_id")
        return updated

    async def _build_since_map(self, accounts: list[Account]) -> dict[str, datetime | None]:
        """Build per-account since times from last saved tweet timestamps."""
        since_map: dict[str, datetime | None] = {}
        default_since = datetime.now(timezone.utc) - timedelta(days=1)

        for account in accounts:
            last_time = await self.storage.get_last_tweet_time(account.username)
            if last_time:
                since_map[account.username] = last_time
                logger.debug(f"@{account.username}: incremental since {last_time.strftime('%m-%d %H:%M')}")
            else:
                since_map[account.username] = default_since
                logger.debug(f"@{account.username}: first run, since 24h ago")

        return since_map

    async def run_daily_job(self) -> DailySummary | None:
        """Run the daily monitoring job.

        This is the main job that:
        1. Ensures all accounts have cached user info
        2. Incrementally fetches only new tweets since last run
        3. Saves tweets to local database
        4. Analyzes recent tweets with LLM
        5. Sends notifications

        Returns:
            DailySummary if successful, None otherwise
        """
        logger.info("Starting daily monitoring job")

        # Get monitored accounts
        accounts = await self.storage.get_accounts()
        if not accounts:
            logger.warning("No accounts to monitor")
            return None

        logger.info(f"Monitoring {len(accounts)} accounts")

        # Step 1: Ensure all accounts have cached user_id
        accounts = await self._ensure_account_info(accounts)

        # Step 2: Build per-account since times for incremental fetch
        since_map = await self._build_since_map(accounts)

        summary_date = datetime.now(timezone.utc)

        # Step 3: Fetch only new tweets
        new_tweets = await self.scraper.get_tweets_for_accounts(accounts, since_map=since_map)
        logger.info(f"Fetched {len(new_tweets)} new tweets from API")

        # Step 4: Save new tweets to local database
        if new_tweets:
            saved = await self.storage.save_tweets(new_tweets)
            logger.info(f"Saved {saved} new tweets to database")

        # Step 5: Read all tweets from last 24h for analysis (from local DB)
        analysis_since = datetime.now(timezone.utc) - timedelta(days=1)
        tweets = await self.storage.get_tweets_since(analysis_since)
        logger.info(f"Loaded {len(tweets)} tweets from local DB for analysis")

        if not tweets:
            logger.info("No tweets to analyze")
            summary = DailySummary(
                date=summary_date,
                accounts_monitored=len(accounts),
                total_tweets=0,
                summary_text="今天监控的账号没有新推文。",
                analysis="无数据可供分析。",
            )
        else:
            # Analyze with LLM
            summary = await self.analyzer.analyze_tweets(tweets, summary_date)

        # Save summary
        await self.storage.save_summary(summary)

        # Send notifications
        for notifier in self.notifiers:
            try:
                await notifier.send_summary(summary)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

        logger.info("Daily monitoring job completed")
        return summary

    async def get_summary(self, date: datetime | None = None) -> DailySummary | None:
        """Get summary for a specific date."""
        if date is None:
            date = datetime.now(timezone.utc)
        return await self.storage.get_summary(date)

    async def get_recent_summaries(self, days: int = 7) -> list[DailySummary]:
        """Get recent summaries."""
        return await self.storage.get_recent_summaries(days)

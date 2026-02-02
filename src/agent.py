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
        self.scraper = XScraper(settings.x_bearer_token)
        self.analyzer = LLMAnalyzer(settings.openai_api_key, settings.openai_model)

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

        # Fetch account info from Twitter
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

    async def run_daily_job(self) -> DailySummary | None:
        """Run the daily monitoring job.

        This is the main job that:
        1. Fetches tweets from all monitored accounts
        2. Analyzes them with LLM
        3. Sends notifications

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

        # Calculate time range (last 24 hours)
        since = datetime.now(timezone.utc) - timedelta(days=1)
        summary_date = datetime.now(timezone.utc)

        # Fetch tweets
        tweets = await self.scraper.get_tweets_for_accounts(accounts, since=since)
        logger.info(f"Fetched {len(tweets)} tweets")

        if not tweets:
            logger.info("No new tweets found")
            # Still create a summary
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

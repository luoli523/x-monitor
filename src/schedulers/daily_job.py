"""Daily job scheduler for running the monitor."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable, Awaitable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger


class DailyJobScheduler:
    """Scheduler for running daily summary jobs."""

    def __init__(self, hour: int = 8, minute: int = 0):
        """Initialize scheduler.

        Args:
            hour: Hour to run daily job (0-23)
            minute: Minute to run daily job (0-59)
        """
        self.scheduler = AsyncIOScheduler()
        self.hour = hour
        self.minute = minute
        self._job_func: Callable[[], Awaitable[None]] | None = None

    def set_job(self, job_func: Callable[[], Awaitable[None]]) -> None:
        """Set the async function to run daily."""
        self._job_func = job_func

    async def _run_job(self) -> None:
        """Wrapper to run the async job."""
        if self._job_func:
            logger.info("Starting scheduled daily job")
            try:
                await self._job_func()
                logger.info("Daily job completed successfully")
            except Exception as e:
                logger.error(f"Daily job failed: {e}")

    def start(self) -> None:
        """Start the scheduler."""
        if not self._job_func:
            raise ValueError("No job function set. Call set_job() first.")

        # Schedule daily job
        trigger = CronTrigger(hour=self.hour, minute=self.minute)
        self.scheduler.add_job(
            self._run_job,
            trigger=trigger,
            id="daily_summary",
            name="Daily X/Twitter Summary",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(f"Scheduler started. Daily job will run at {self.hour:02d}:{self.minute:02d}")

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    async def run_now(self) -> None:
        """Run the job immediately (for testing)."""
        if self._job_func:
            await self._job_func()
        else:
            raise ValueError("No job function set")

    def get_next_run_time(self) -> datetime | None:
        """Get the next scheduled run time."""
        job = self.scheduler.get_job("daily_summary")
        if job:
            return job.next_run_time
        return None

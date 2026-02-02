"""Storage layer using SQLite for persistence."""

import json
from datetime import datetime
from pathlib import Path

import aiosqlite
from loguru import logger

from src.models import Account, Tweet, DailySummary


class Storage:
    """SQLite-based storage for accounts and summaries."""

    def __init__(self, db_path: str):
        """Initialize storage with database path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        """Create database tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY,
                    user_id TEXT,
                    display_name TEXT,
                    description TEXT,
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    accounts_monitored INTEGER,
                    total_tweets INTEGER,
                    summary_text TEXT,
                    analysis TEXT,
                    key_insights TEXT,
                    generated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_summaries_date ON summaries(date);
            """)
            await db.commit()
            logger.info(f"Database initialized at {self.db_path}")

    # Account management
    async def add_account(self, account: Account) -> bool:
        """Add an account to monitor."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO accounts
                    (username, user_id, display_name, description, added_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        account.username,
                        account.user_id,
                        account.display_name,
                        account.description,
                        account.added_at.isoformat(),
                    ),
                )
                await db.commit()
                logger.info(f"Added account: @{account.username}")
                return True
            except Exception as e:
                logger.error(f"Failed to add account {account.username}: {e}")
                return False

    async def remove_account(self, username: str) -> bool:
        """Remove an account from monitoring."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM accounts WHERE username = ?", (username,)
            )
            await db.commit()
            if cursor.rowcount > 0:
                logger.info(f"Removed account: @{username}")
                return True
            return False

    async def get_accounts(self) -> list[Account]:
        """Get all monitored accounts."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM accounts ORDER BY added_at")
            rows = await cursor.fetchall()

            return [
                Account(
                    username=row["username"],
                    user_id=row["user_id"],
                    display_name=row["display_name"],
                    description=row["description"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                )
                for row in rows
            ]

    async def get_account(self, username: str) -> Account | None:
        """Get a specific account."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM accounts WHERE username = ?", (username,)
            )
            row = await cursor.fetchone()

            if row:
                return Account(
                    username=row["username"],
                    user_id=row["user_id"],
                    display_name=row["display_name"],
                    description=row["description"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                )
            return None

    # Summary management
    async def save_summary(self, summary: DailySummary) -> bool:
        """Save a daily summary."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO summaries
                    (date, accounts_monitored, total_tweets, summary_text, analysis, key_insights, generated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        summary.date.strftime("%Y-%m-%d"),
                        summary.accounts_monitored,
                        summary.total_tweets,
                        summary.summary_text,
                        summary.analysis,
                        json.dumps(summary.key_insights, ensure_ascii=False),
                        summary.generated_at.isoformat(),
                    ),
                )
                await db.commit()
                logger.info(f"Saved summary for {summary.date.strftime('%Y-%m-%d')}")
                return True
            except Exception as e:
                logger.error(f"Failed to save summary: {e}")
                return False

    async def get_summary(self, date: datetime) -> DailySummary | None:
        """Get summary for a specific date."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM summaries WHERE date = ?",
                (date.strftime("%Y-%m-%d"),),
            )
            row = await cursor.fetchone()

            if row:
                return DailySummary(
                    date=datetime.strptime(row["date"], "%Y-%m-%d"),
                    accounts_monitored=row["accounts_monitored"],
                    total_tweets=row["total_tweets"],
                    summary_text=row["summary_text"],
                    analysis=row["analysis"],
                    key_insights=json.loads(row["key_insights"]) if row["key_insights"] else [],
                    generated_at=datetime.fromisoformat(row["generated_at"]),
                )
            return None

    async def get_recent_summaries(self, days: int = 7) -> list[DailySummary]:
        """Get recent summaries."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM summaries ORDER BY date DESC LIMIT ?", (days,)
            )
            rows = await cursor.fetchall()

            return [
                DailySummary(
                    date=datetime.strptime(row["date"], "%Y-%m-%d"),
                    accounts_monitored=row["accounts_monitored"],
                    total_tweets=row["total_tweets"],
                    summary_text=row["summary_text"],
                    analysis=row["analysis"],
                    key_insights=json.loads(row["key_insights"]) if row["key_insights"] else [],
                    generated_at=datetime.fromisoformat(row["generated_at"]),
                )
                for row in rows
            ]

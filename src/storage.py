"""Storage layer using SQLite for persistence."""

import json
from datetime import datetime
from pathlib import Path

import aiosqlite
from loguru import logger

from src.models import Account, Tweet, DailySummary


class Storage:
    """Storage for accounts (JSON file) and summaries (SQLite)."""

    def __init__(self, db_path: str, accounts_config_path: str = "config/accounts.json"):
        """Initialize storage with database path and accounts config path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.accounts_config_path = Path(accounts_config_path)
        # Ensure config directory exists
        self.accounts_config_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        """Create database tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
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
        
        # Initialize accounts config file if it doesn't exist
        if not self.accounts_config_path.exists():
            self.accounts_config_path.write_text(json.dumps({"accounts": []}, indent=2, ensure_ascii=False))
            logger.info(f"Created accounts config file at {self.accounts_config_path}")

    # Account management (JSON-based)
    def _load_accounts_config(self) -> dict:
        """Load accounts configuration from JSON file."""
        try:
            if self.accounts_config_path.exists():
                content = self.accounts_config_path.read_text(encoding="utf-8")
                return json.loads(content)
            return {"accounts": []}
        except Exception as e:
            logger.error(f"Failed to load accounts config: {e}")
            return {"accounts": []}

    def _save_accounts_config(self, config: dict) -> bool:
        """Save accounts configuration to JSON file."""
        try:
            self.accounts_config_path.write_text(
                json.dumps(config, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save accounts config: {e}")
            return False

    async def add_account(self, account: Account) -> bool:
        """Add an account to the JSON config file."""
        try:
            config = self._load_accounts_config()
            
            # Check if account already exists
            existing_usernames = {acc["username"] for acc in config["accounts"]}
            if account.username in existing_usernames:
                logger.warning(f"Account @{account.username} already exists in config")
                return True
            
            # Add new account
            config["accounts"].append({
                "username": account.username,
                "note": account.display_name or account.description or ""
            })
            
            if self._save_accounts_config(config):
                logger.info(f"Added account to config: @{account.username}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to add account {account.username}: {e}")
            return False

    async def remove_account(self, username: str) -> bool:
        """Remove an account from the JSON config file."""
        try:
            config = self._load_accounts_config()
            original_count = len(config["accounts"])
            
            # Filter out the account
            config["accounts"] = [
                acc for acc in config["accounts"]
                if acc["username"] != username
            ]
            
            if len(config["accounts"]) < original_count:
                if self._save_accounts_config(config):
                    logger.info(f"Removed account from config: @{username}")
                    return True
            else:
                logger.warning(f"Account @{username} not found in config")
            return False
        except Exception as e:
            logger.error(f"Failed to remove account {username}: {e}")
            return False

    async def get_accounts(self) -> list[Account]:
        """Get all monitored accounts from JSON config file."""
        try:
            config = self._load_accounts_config()
            accounts = []
            
            for acc_data in config["accounts"]:
                username = acc_data.get("username", "").strip()
                if username:
                    accounts.append(
                        Account(
                            username=username,
                            display_name=acc_data.get("note", ""),
                            description=acc_data.get("note", ""),
                        )
                    )
            
            logger.info(f"Loaded {len(accounts)} accounts from config file")
            return accounts
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            return []

    async def get_account(self, username: str) -> Account | None:
        """Get a specific account from JSON config file."""
        try:
            config = self._load_accounts_config()
            
            for acc_data in config["accounts"]:
                if acc_data.get("username") == username:
                    return Account(
                        username=username,
                        display_name=acc_data.get("note", ""),
                        description=acc_data.get("note", ""),
                    )
            return None
        except Exception as e:
            logger.error(f"Failed to get account {username}: {e}")
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

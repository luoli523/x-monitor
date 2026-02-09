"""Storage layer using SQLite for persistence."""

import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
from loguru import logger

from src.models import Account, Tweet, DailySummary


class Storage:
    """Storage for accounts (JSON file), tweets and summaries (SQLite)."""

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

                CREATE TABLE IF NOT EXISTS tweets (
                    tweet_id TEXT PRIMARY KEY,
                    author_username TEXT NOT NULL,
                    author_display_name TEXT,
                    content TEXT,
                    created_at TEXT NOT NULL,
                    likes INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0,
                    replies INTEGER DEFAULT 0,
                    views INTEGER,
                    url TEXT,
                    is_retweet BOOLEAN DEFAULT 0,
                    is_reply BOOLEAN DEFAULT 0,
                    media_urls TEXT,
                    fetched_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tweets_author ON tweets(author_username);
                CREATE INDEX IF NOT EXISTS idx_tweets_created ON tweets(created_at);
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

            # Add new account with cached user info
            entry = {
                "username": account.username,
                "note": account.description or account.display_name or "",
            }
            if account.user_id:
                entry["user_id"] = account.user_id
            if account.display_name:
                entry["display_name"] = account.display_name
            if account.description:
                entry["description"] = account.description

            config["accounts"].append(entry)

            if self._save_accounts_config(config):
                logger.info(f"Added account to config: @{account.username}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to add account {account.username}: {e}")
            return False

    async def update_account_info(
        self, username: str, user_id: str, display_name: str | None, description: str | None
    ) -> bool:
        """Update cached user info for an account in JSON config."""
        try:
            config = self._load_accounts_config()
            for acc in config["accounts"]:
                if acc["username"] == username:
                    acc["user_id"] = user_id
                    if display_name:
                        acc["display_name"] = display_name
                    if description:
                        acc["description"] = description
                    return self._save_accounts_config(config)
            logger.warning(f"Account @{username} not found in config for update")
            return False
        except Exception as e:
            logger.error(f"Failed to update account info for {username}: {e}")
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
                            user_id=acc_data.get("user_id"),
                            display_name=acc_data.get("display_name") or acc_data.get("note", ""),
                            description=acc_data.get("description") or acc_data.get("note", ""),
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
                        user_id=acc_data.get("user_id"),
                        display_name=acc_data.get("display_name") or acc_data.get("note", ""),
                        description=acc_data.get("description") or acc_data.get("note", ""),
                    )
            return None
        except Exception as e:
            logger.error(f"Failed to get account {username}: {e}")
            return None

    # Tweet management
    async def save_tweets(self, tweets: list[Tweet]) -> int:
        """Save tweets to database. Returns number of new tweets saved."""
        if not tweets:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        saved = 0
        async with aiosqlite.connect(self.db_path) as db:
            for tweet in tweets:
                try:
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO tweets
                        (tweet_id, author_username, author_display_name, content, created_at,
                         likes, retweets, replies, views, url, is_retweet, is_reply, media_urls, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tweet.tweet_id,
                            tweet.author_username,
                            tweet.author_display_name,
                            tweet.content,
                            tweet.created_at.isoformat(),
                            tweet.likes,
                            tweet.retweets,
                            tweet.replies,
                            tweet.views,
                            tweet.url,
                            tweet.is_retweet,
                            tweet.is_reply,
                            json.dumps(tweet.media_urls) if tweet.media_urls else "[]",
                            now,
                        ),
                    )
                    if db.total_changes:
                        saved += 1
                except Exception as e:
                    logger.error(f"Failed to save tweet {tweet.tweet_id}: {e}")
            await db.commit()
        if saved:
            logger.info(f"Saved {saved} new tweets to database")
        return saved

    async def get_last_tweet_time(self, username: str) -> datetime | None:
        """Get the most recent tweet time for an account."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT MAX(created_at) FROM tweets WHERE author_username = ?",
                (username,),
            )
            row = await cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
        return None

    async def get_tweets_since(self, since: datetime, username: str | None = None) -> list[Tweet]:
        """Get tweets from local database since a given time."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if username:
                cursor = await db.execute(
                    "SELECT * FROM tweets WHERE created_at >= ? AND author_username = ? ORDER BY created_at DESC",
                    (since.isoformat(), username),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM tweets WHERE created_at >= ? ORDER BY created_at DESC",
                    (since.isoformat(),),
                )
            rows = await cursor.fetchall()

            return [
                Tweet(
                    tweet_id=row["tweet_id"],
                    author_username=row["author_username"],
                    author_display_name=row["author_display_name"],
                    content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    likes=row["likes"],
                    retweets=row["retweets"],
                    replies=row["replies"],
                    views=row["views"],
                    url=row["url"],
                    is_retweet=bool(row["is_retweet"]),
                    is_reply=bool(row["is_reply"]),
                    media_urls=json.loads(row["media_urls"]) if row["media_urls"] else [],
                )
                for row in rows
            ]
    
    async def get_tweets_between(self, start: datetime, end: datetime, username: str | None = None) -> list[Tweet]:
        """Get tweets from local database between two times.
        
        Args:
            start: Start time (inclusive)
            end: End time (inclusive)
            username: Optional username filter
            
        Returns:
            List of tweets sorted by creation time (newest first)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if username:
                cursor = await db.execute(
                    "SELECT * FROM tweets WHERE created_at >= ? AND created_at <= ? AND author_username = ? ORDER BY created_at DESC",
                    (start.isoformat(), end.isoformat(), username),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM tweets WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC",
                    (start.isoformat(), end.isoformat()),
                )
            rows = await cursor.fetchall()

            return [
                Tweet(
                    tweet_id=row["tweet_id"],
                    author_username=row["author_username"],
                    author_display_name=row["author_display_name"],
                    content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    likes=row["likes"],
                    retweets=row["retweets"],
                    replies=row["replies"],
                    views=row["views"],
                    url=row["url"],
                    is_retweet=bool(row["is_retweet"]),
                    is_reply=bool(row["is_reply"]),
                    media_urls=json.loads(row["media_urls"]) if row["media_urls"] else [],
                )
                for row in rows
            ]

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

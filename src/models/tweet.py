"""Tweet and account data models."""

from datetime import datetime
from pydantic import BaseModel, Field


class Account(BaseModel):
    """X/Twitter account to monitor."""

    username: str = Field(..., description="Twitter username without @")
    user_id: str | None = Field(default=None, description="Twitter user ID")
    display_name: str | None = Field(default=None, description="Display name")
    description: str | None = Field(default=None, description="Account bio")
    added_at: datetime = Field(default_factory=datetime.now)


class Tweet(BaseModel):
    """A single tweet from a monitored account."""

    tweet_id: str = Field(..., description="Unique tweet ID")
    author_username: str = Field(..., description="Author's username")
    author_display_name: str | None = Field(default=None)
    content: str = Field(..., description="Tweet text content")
    created_at: datetime = Field(..., description="Tweet creation time")
    likes: int = Field(default=0)
    retweets: int = Field(default=0)
    replies: int = Field(default=0)
    views: int | None = Field(default=None)
    url: str = Field(default="")
    is_retweet: bool = Field(default=False)
    is_reply: bool = Field(default=False)
    media_urls: list[str] = Field(default_factory=list)

    @property
    def engagement_score(self) -> int:
        """Calculate engagement score."""
        return self.likes + self.retweets * 2 + self.replies * 3


class DailySummary(BaseModel):
    """Daily summary of monitored accounts."""

    date: datetime = Field(..., description="Summary date")
    accounts_monitored: int = Field(default=0)
    total_tweets: int = Field(default=0)
    tweets: list[Tweet] = Field(default_factory=list)
    summary_text: str = Field(default="", description="LLM-generated summary")
    analysis: str = Field(default="", description="LLM-generated analysis")
    key_insights: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)

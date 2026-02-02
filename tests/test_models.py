"""Tests for data models."""

from datetime import datetime

import pytest

from src.models import Tweet, Account, DailySummary


def test_account_creation():
    """Test Account model creation."""
    account = Account(username="testuser")
    assert account.username == "testuser"
    assert account.user_id is None


def test_tweet_engagement_score():
    """Test Tweet engagement score calculation."""
    tweet = Tweet(
        tweet_id="123",
        author_username="test",
        content="Hello world",
        created_at=datetime.now(),
        likes=10,
        retweets=5,
        replies=2,
    )
    # likes + retweets*2 + replies*3 = 10 + 10 + 6 = 26
    assert tweet.engagement_score == 26


def test_daily_summary_defaults():
    """Test DailySummary default values."""
    summary = DailySummary(date=datetime.now())
    assert summary.accounts_monitored == 0
    assert summary.total_tweets == 0
    assert summary.tweets == []
    assert summary.key_insights == []

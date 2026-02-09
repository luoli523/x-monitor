# X Monitor

AI Agent for monitoring X.com (Twitter) accounts and generating daily summaries with LLM-powered analysis.

## Features

- 📱 Monitor multiple X/Twitter accounts
- 🤖 LLM-powered multi-dimensional analysis using OpenAI GPT
- 📊 Daily summaries with key insights extraction
- 🔄 Incremental tweet fetching (only fetch new tweets since last run)
- 💾 User info caching (reduce API calls per run)
- ⚡ Smart rate limiting with skip-on-limit strategy
- 📧 Email notifications (HTML formatted reports)
- 📲 Telegram bot notifications (auto message chunking)
- ⏰ Cron-based scheduled daily jobs
- 🗄️ Hybrid storage: JSON config + SQLite data persistence

## Installation

```bash
# Clone the repository
cd x-monitor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Configuration

### 1. Environment variables

Copy and edit the example file:

```bash
cp .env.example .env
```

**Required:**

| Variable | Description |
|----------|-------------|
| `X_BEARER_TOKEN` | X API Bearer Token ([Developer Portal](https://developer.twitter.com/)) |
| `OPENAI_API_KEY` | OpenAI API Key ([Platform](https://platform.openai.com/)) |

**Optional — OpenAI:**

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_MODEL` | `gpt-4-turbo-preview` | Model to use for analysis |
| `OPENAI_MAX_COMPLETION_TOKENS` | `16000` | Max completion tokens |
| `OPENAI_TEMPERATURE` | *(model default)* | Temperature (leave empty for reasoning models) |

**Optional — Telegram notifications:**

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Target chat ID |

**Optional — Email notifications:**

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port (TLS) |
| `SMTP_USER` | | Sender email |
| `SMTP_PASSWORD` | | App-specific password |
| `EMAIL_TO` | | Recipient email |

**Optional — Scheduling & Rate limiting:**

| Variable | Default | Description |
|----------|---------|-------------|
| `SUMMARY_CRON_HOUR` | `8` | Daily job hour (0-23) |
| `SUMMARY_CRON_MINUTE` | `0` | Daily job minute (0-59) |
| `DATABASE_PATH` | `data/x_monitor.db` | SQLite database path |
| `RATE_LIMIT_DELAY` | `2.0` | Delay between accounts (seconds) |
| `RATE_LIMIT_BATCH_SIZE` | `10` | Accounts per batch |
| `RATE_LIMIT_BATCH_DELAY` | `10.0` | Delay between batches (seconds) |

### 2. Accounts to monitor

Edit `config/accounts.json` to add Twitter accounts:

```json
{
  "accounts": [
    {
      "username": "elonmusk",
      "note": "Tesla/SpaceX CEO"
    },
    {
      "username": "OpenAI",
      "note": "AI Research Company"
    }
  ]
}
```

When accounts are added via CLI (`x-monitor add`), `user_id`, `display_name`, and `description` are automatically fetched from the API and cached in this file, reducing API calls on subsequent runs.

## Usage

### List monitored accounts

```bash
x-monitor list
```

### Add/Remove accounts

```bash
# Add account (fetches and caches user info from API)
x-monitor add karpathy

# Remove account
x-monitor remove karpathy
```

### Run analysis immediately

```bash
x-monitor run
```

Fetches new tweets incrementally, analyzes with LLM, and sends notifications.

### Regenerate report from database

```bash
# Regenerate report for today (no API calls, uses cached tweets)
x-monitor regenerate

# Regenerate report for a specific date
x-monitor regenerate --date 2026-02-08

# Regenerate and send notifications
x-monitor regenerate --notify
```

This command reads tweets already stored in the local database and regenerates the LLM analysis without making any X API calls. Useful for:
- Testing different analysis prompts
- Updating reports without consuming API quota
- Generating historical reports

### Start as a scheduled service

```bash
x-monitor serve
```

Runs the daily job at the configured time (default: 8:00 AM). Keeps running until Ctrl+C.

### View history

```bash
x-monitor history --days 7
```

## Architecture

```
CLI (main.py)
    │
    ▼
Agent (agent.py) ─── Main orchestrator
    │
    ├── Storage (storage.py) ─── Accounts (JSON) + Tweets/Summaries (SQLite)
    ├── Scraper (x_scraper.py) ─── XDK API calls with rate limiting
    ├── Analyzer (llm_analyzer.py) ─── OpenAI LLM analysis
    └── Notifiers (email + telegram) ─── Send formatted reports
```

**Daily job flow:**

1. Load accounts from `config/accounts.json`
2. Ensure all accounts have cached `user_id` (fetch from API if missing)
3. Build per-account "since" times from last saved tweet timestamps
4. Fetch only **new** tweets incrementally from X API
5. Save tweets to SQLite database
6. Load all tweets from last 24h from local database
7. Send to LLM for multi-dimensional analysis
8. Save summary to database
9. Send notifications (Email + Telegram, if configured)

## Project Structure

```
x-monitor/
├── src/
│   ├── scrapers/       # X/Twitter data fetching (XDK)
│   ├── analyzers/      # LLM multi-dimensional analysis
│   ├── notifiers/      # Email & Telegram notifications
│   ├── schedulers/     # Cron-based job scheduling
│   ├── models/         # Pydantic data models
│   ├── agent.py        # Main orchestrator
│   ├── config.py       # Settings management (pydantic-settings)
│   ├── storage.py      # Hybrid storage (JSON + SQLite)
│   └── main.py         # CLI entry point (Click)
├── config/             # accounts.json
├── data/               # SQLite database
├── logs/               # Log files
└── tests/              # Test files
```

## Tech Stack

- **X API**: [XDK](https://pypi.org/project/xdk/) (official SDK)
- **LLM**: OpenAI GPT
- **CLI**: Click
- **Data validation**: Pydantic
- **Storage**: aiosqlite + JSON
- **Notifications**: python-telegram-bot, aiosmtplib
- **Scheduling**: APScheduler
- **Logging**: Loguru

## License

MIT

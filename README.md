# X Monitor

AI Agent for monitoring X.com (Twitter) accounts and generating daily summaries with LLM-powered analysis.

## Features

- 📱 Monitor multiple X/Twitter accounts
- 🤖 LLM-powered analysis using OpenAI GPT
- 📊 Daily summaries with key insights
- 📧 Email notifications
- 📲 Telegram bot notifications
- ⏰ Scheduled daily jobs
- 💾 SQLite storage for history

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

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in your credentials:

- **X_BEARER_TOKEN**: Get from [Twitter Developer Portal](https://developer.twitter.com/)
- **OPENAI_API_KEY**: Get from [OpenAI](https://platform.openai.com/)
- **TELEGRAM_BOT_TOKEN**: Create via [@BotFather](https://t.me/BotFather)
- **SMTP credentials**: For email notifications

## Usage

### Add accounts to monitor

```bash
x-monitor add elonmusk
x-monitor add OpenAI
```

### List monitored accounts

```bash
x-monitor list
```

### Run analysis immediately

```bash
x-monitor run
```

### Start as a scheduled service

```bash
x-monitor serve
```

This will run the daily job at the configured time (default: 8:00 AM).

### View history

```bash
x-monitor history --days 7
```

## Project Structure

```
x-monitor/
├── src/
│   ├── scrapers/       # X/Twitter data fetching
│   ├── analyzers/      # LLM analysis
│   ├── notifiers/      # Email & Telegram notifications
│   ├── schedulers/     # Job scheduling
│   ├── models/         # Data models
│   ├── agent.py        # Main orchestrator
│   ├── config.py       # Settings management
│   ├── storage.py      # SQLite persistence
│   └── main.py         # CLI entry point
├── config/             # Configuration files
├── data/               # Database files
├── logs/               # Log files
└── tests/              # Test files
```

## License

MIT

# X Monitor

AI Agent for monitoring X.com (Twitter) accounts and generating daily summaries with LLM-powered analysis.

## Features

- 📱 Monitor multiple X/Twitter accounts
- 🤖 LLM-powered multi-dimensional analysis using OpenAI GPT
- 📊 Daily summaries with key insights extraction
- 🔄 Incremental tweet fetching (only fetch new tweets since last run)
- 💾 User info caching (reduce API calls per run)
- ⚡ Smart rate limiting with skip-on-limit strategy
- 📄 Auto-export Markdown reports to `output/` directory
- 🔁 Regenerate reports from database (zero API calls)
- 📧 Email notifications (beautiful HTML formatted reports)
- 📲 Telegram bot notifications (smart chunking, full content)
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

This command reads tweets already stored in the local database and regenerates the LLM analysis **without making any X API calls**. 

**Use cases:**
- 🧪 **Testing prompts** - Modified `src/analyzers/llm_analyzer.py`? Regenerate to see new analysis instantly
- 💰 **Save API quota** - No X API or additional OpenAI calls (only LLM analysis)
- 📜 **Historical reports** - Generate reports for past dates from cached data
- 🔧 **Fix errors** - If a report generation failed, rerun without re-fetching tweets

**What happens:**
1. Query all tweets from database for the specified date range
2. Send to LLM for fresh analysis using current prompts
3. Update database summary record
4. Generate/update Markdown report in `output/`
5. Optionally send notifications (with `--notify` flag)

### Start as a scheduled service

```bash
x-monitor serve
```

Runs the daily job at the configured time (default: 8:00 AM). Keeps running until Ctrl+C.

### View history

```bash
x-monitor history --days 7
```

## Output & Notifications

X Monitor generates reports in **three formats**, all sharing the same structure:

### 1. Markdown Files (Local)

**Location:** `output/report_YYYY-MM-DD.md`

- Auto-generated after each run
- Git-ignored (`.gitignore` configured)
- Full analysis content with formatting preserved
- Easy to read, search, and version control manually if needed

### 2. Email (HTML + Plain Text)

**Format:** Beautiful HTML email with modern styling

- **Metadata card** - Date, account count, tweet count, generation time
- **Full analysis** - All analysis dimensions (not truncated)
- **Key insights** - Highlighted in green cards
- **Responsive design** - Works across email clients
- **Plain text fallback** - For email clients that don't support HTML

**Sample structure:**
```
📊 X/Twitter 每日监控报告
┌─────────────────────────────┐
│ 日期：2026年02月09日           │
│ 监控账号：14 个                │
│ 推文数量：147 条               │
│ 生成时间：2026-02-09 18:39:19 │
└─────────────────────────────┘

[Full analysis content...]

关键洞察
✓ Insight 1
✓ Insight 2
```

### 3. Telegram (Plain Text)

**Format:** Plain text with Unicode separators

- **Auto-chunking** - Messages >4096 chars split intelligently by line
- **Full content** - No truncation (previously limited to 3000 chars)
- **Reliable** - No Markdown parsing errors (removed complex escaping)
- **Numbered parts** - Multi-part messages labeled `(续 2/3)`

**Why plain text?** Telegram's MarkdownV2 has complex escaping rules that frequently caused parsing errors. Plain text is 100% reliable while maintaining readability.

### Notification Configuration

Configure in `.env`:

```bash
# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_TO=recipient@example.com

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Notifications are **optional** - leave variables unset to disable.

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
9. **Export Markdown report to `output/report_YYYY-MM-DD.md`**
10. Send notifications (Email + Telegram, if configured)

**Report formats:**
- 📄 **Markdown file** - Saved to `output/` directory (git-ignored)
- 📧 **Email (HTML)** - Modern styled HTML with full analysis content
- 📲 **Telegram (Plain text)** - Auto-chunked for messages >4096 chars

All three formats share the same structure: metadata + full analysis + key insights.

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
├── config/             # Account list (accounts.json)
├── data/               # SQLite database (tweets, summaries)
├── output/             # Generated Markdown reports (git-ignored)
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

"""Main entry point for X Monitor."""

import asyncio
import sys
from pathlib import Path

import click
from loguru import logger

from src.config import get_settings
from src.agent import XMonitorAgent
from src.schedulers import DailyJobScheduler


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/x_monitor_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG",
)


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """X Monitor - AI Agent for monitoring X/Twitter accounts."""
    ctx.ensure_object(dict)
    ctx.obj["settings"] = get_settings()


@cli.command()
@click.argument("username")
@click.pass_context
def add(ctx: click.Context, username: str) -> None:
    """Add an account to monitor."""

    async def _add() -> None:
        settings = ctx.obj["settings"]
        agent = XMonitorAgent(settings)
        await agent.initialize()

        account = await agent.add_account(username)
        if account:
            click.echo(f"✅ Added @{account.username} ({account.display_name})")
        else:
            click.echo(f"❌ Failed to add @{username}")
            sys.exit(1)

    asyncio.run(_add())


@cli.command()
@click.argument("username")
@click.pass_context
def remove(ctx: click.Context, username: str) -> None:
    """Remove an account from monitoring."""

    async def _remove() -> None:
        settings = ctx.obj["settings"]
        agent = XMonitorAgent(settings)
        await agent.initialize()

        if await agent.remove_account(username):
            click.echo(f"✅ Removed @{username}")
        else:
            click.echo(f"❌ Account @{username} not found")
            sys.exit(1)

    asyncio.run(_remove())


@cli.command("list")
@click.pass_context
def list_accounts(ctx: click.Context) -> None:
    """List all monitored accounts."""

    async def _list() -> None:
        settings = ctx.obj["settings"]
        agent = XMonitorAgent(settings)
        await agent.initialize()

        accounts = await agent.list_accounts()
        if not accounts:
            click.echo("No accounts being monitored.")
            return

        click.echo(f"\n📱 Monitoring {len(accounts)} accounts:\n")
        for acc in accounts:
            click.echo(f"  • @{acc.username} ({acc.display_name or 'N/A'})")
            if acc.description:
                click.echo(f"    {acc.description[:60]}...")
        click.echo()

    asyncio.run(_list())


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Run the daily job immediately."""

    async def _run() -> None:
        settings = ctx.obj["settings"]
        agent = XMonitorAgent(settings)
        await agent.initialize()

        click.echo("🚀 Running daily monitoring job...")
        summary = await agent.run_daily_job()

        if summary:
            click.echo(f"\n✅ Job completed!")
            click.echo(f"   Accounts: {summary.accounts_monitored}")
            click.echo(f"   Tweets: {summary.total_tweets}")
            click.echo(f"\n📊 Analysis:\n{summary.analysis[:500]}...")
        else:
            click.echo("❌ Job failed or no accounts to monitor")

    asyncio.run(_run())


@cli.command()
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start the scheduler and run as a service."""

    async def _serve() -> None:
        settings = ctx.obj["settings"]
        agent = XMonitorAgent(settings)
        await agent.initialize()

        scheduler = DailyJobScheduler(
            hour=settings.summary_cron_hour,
            minute=settings.summary_cron_minute,
        )
        scheduler.set_job(agent.run_daily_job)
        scheduler.start()

        next_run = scheduler.get_next_run_time()
        click.echo(f"🚀 X Monitor service started")
        click.echo(f"⏰ Next scheduled run: {next_run}")
        click.echo("Press Ctrl+C to stop...")

        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            scheduler.stop()
            click.echo("\n👋 Service stopped")

    asyncio.run(_serve())


@cli.command()
@click.option("--days", "-d", default=7, help="Number of days to show")
@click.pass_context
def history(ctx: click.Context, days: int) -> None:
    """Show recent summary history."""

    async def _history() -> None:
        settings = ctx.obj["settings"]
        agent = XMonitorAgent(settings)
        await agent.initialize()

        summaries = await agent.get_recent_summaries(days)
        if not summaries:
            click.echo("No summaries found.")
            return

        click.echo(f"\n📊 Recent {len(summaries)} summaries:\n")
        for s in summaries:
            date_str = s.date.strftime("%Y-%m-%d")
            click.echo(f"  📅 {date_str}")
            click.echo(f"     Accounts: {s.accounts_monitored}, Tweets: {s.total_tweets}")
            if s.key_insights:
                click.echo(f"     Key insight: {s.key_insights[0][:60]}...")
            click.echo()

    asyncio.run(_history())


@cli.command()
@click.option("--date", "-d", help="Date to regenerate report for (YYYY-MM-DD), default: today")
@click.option("--notify", "-n", is_flag=True, help="Send notifications after regeneration")
@click.pass_context
def regenerate(ctx: click.Context, date: str | None, notify: bool) -> None:
    """Regenerate report from database without fetching new tweets.
    
    This command uses tweets already stored in the local database to
    regenerate the LLM analysis. Useful for:
    - Updating analysis with improved prompts
    - Generating reports without API calls
    - Testing different analysis approaches
    """

    async def _regenerate() -> None:
        from datetime import datetime, timezone
        
        settings = ctx.obj["settings"]
        agent = XMonitorAgent(settings)
        await agent.initialize()

        # Parse date if provided
        target_date = None
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                click.echo(f"❌ Invalid date format: {date}. Use YYYY-MM-DD")
                sys.exit(1)
        
        date_str = target_date.strftime("%Y-%m-%d") if target_date else "today"
        click.echo(f"🔄 Regenerating report for {date_str} from database...")
        
        summary = await agent.regenerate_report_from_db(
            date=target_date,
            send_notifications=notify
        )

        if summary:
            click.echo(f"\n✅ Report regenerated!")
            click.echo(f"   Date: {summary.date.strftime('%Y-%m-%d')}")
            click.echo(f"   Tweets analyzed: {summary.total_tweets}")
            click.echo(f"   Report saved to: output/report_{summary.date.strftime('%Y-%m-%d')}.md")
            if notify:
                click.echo(f"   📧 Notifications sent")
            click.echo(f"\n📊 Analysis preview:\n{summary.analysis[:300]}...")
        else:
            click.echo(f"❌ No tweets found in database for {date_str}")
            sys.exit(1)

    asyncio.run(_regenerate())


def main() -> None:
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()

"""Telegram notification service."""

from loguru import logger
from telegram import Bot
from telegram.constants import ParseMode

from src.models import DailySummary


class TelegramNotifier:
    """Send notifications via Telegram bot."""

    def __init__(self, bot_token: str, chat_id: str):
        """Initialize Telegram notifier."""
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    def _format_summary_message(self, summary: DailySummary) -> str:
        """Format summary for Telegram (Markdown)."""
        date_str = summary.date.strftime("%Y年%m月%d日")

        message = f"""📊 *X/Twitter 每日监控报告*
📅 *日期:* {date_str}

📱 *监控账号:* {summary.accounts_monitored}
📝 *推文数量:* {summary.total_tweets}

"""

        if summary.key_insights:
            message += "🔑 *关键洞察:*\n"
            for i, insight in enumerate(summary.key_insights, 1):
                # Escape markdown special characters
                safe_insight = insight.replace("*", "\\*").replace("_", "\\_")
                message += f"{i}\\. {safe_insight}\n"
            message += "\n"

        # Truncate analysis for Telegram (max 4096 chars)
        analysis = summary.analysis
        if len(analysis) > 3000:
            analysis = analysis[:3000] + "\n\n...(内容过长，已截断)"

        # Escape markdown
        analysis = analysis.replace("*", "\\*").replace("_", "\\_")
        message += f"📋 *详细分析:*\n{analysis}"

        return message

    async def send_summary(self, summary: DailySummary) -> bool:
        """Send daily summary via Telegram.

        Args:
            summary: The daily summary to send

        Returns:
            True if sent successfully, False otherwise
        """
        message = self._format_summary_message(summary)

        try:
            # Split long messages if needed
            if len(message) > 4096:
                # Send in chunks
                chunks = [message[i : i + 4000] for i in range(0, len(message), 4000)]
                for i, chunk in enumerate(chunks):
                    if i > 0:
                        chunk = f"(续 {i + 1}/{len(chunks)})\n\n" + chunk
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=chunk,
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )
            else:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )

            logger.info(f"Telegram message sent to chat {self.chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            # Try sending without markdown as fallback
            try:
                plain_message = f"""📊 X/Twitter 每日监控报告
📅 日期: {summary.date.strftime("%Y年%m月%d日")}
📱 监控账号: {summary.accounts_monitored}
📝 推文数量: {summary.total_tweets}

{summary.analysis[:3500]}"""
                await self.bot.send_message(chat_id=self.chat_id, text=plain_message)
                logger.info("Telegram message sent (plain text fallback)")
                return True
            except Exception as e2:
                logger.error(f"Failed to send plain Telegram message: {e2}")
                return False

"""Telegram notification service."""

from loguru import logger
from telegram import Bot

from src.models import DailySummary


class TelegramNotifier:
    """Send notifications via Telegram bot."""

    def __init__(self, bot_token: str, chat_id: str):
        """Initialize Telegram notifier."""
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send_summary(self, summary: DailySummary) -> bool:
        """Send daily summary via Telegram.

        Args:
            summary: The daily summary to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Build plain text message (no complex escaping needed)
            date_str = summary.date.strftime("%Y年%m月%d日")
            gen_time = summary.generated_at.strftime("%Y-%m-%d %H:%M:%S")
            
            message = f"""📊 X/Twitter 每日监控报告

日期：{date_str}
监控账号：{summary.accounts_monitored} 个
推文数量：{summary.total_tweets} 条
生成时间：{gen_time}

━━━━━━━━━━━━━━━

{summary.analysis}

━━━━━━━━━━━━━━━

关键洞察
"""

            if summary.key_insights:
                for i, insight in enumerate(summary.key_insights, 1):
                    message += f"{i}. {insight}\n"
            else:
                message += "（无关键洞察）\n"

            message += f"""
━━━━━━━━━━━━━━━

本报告由 X-Monitor AI Agent 自动生成
"""

            # Split long messages if needed (Telegram max 4096 chars)
            if len(message) > 4096:
                # Send in chunks
                chunks = []
                current_chunk = ""
                
                for line in message.split("\n"):
                    if len(current_chunk) + len(line) + 1 > 4000:
                        chunks.append(current_chunk)
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                for i, chunk in enumerate(chunks):
                    if i > 0:
                        chunk = f"📄 (续 {i + 1}/{len(chunks)})\n\n" + chunk
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=chunk,
                    )
            else:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                )

            logger.info(f"Telegram message sent to chat {self.chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

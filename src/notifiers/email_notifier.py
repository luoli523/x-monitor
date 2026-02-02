"""Email notification service."""

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from loguru import logger

from src.models import DailySummary


class EmailNotifier:
    """Send notifications via email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        to_email: str,
    ):
        """Initialize email notifier."""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.to_email = to_email

    def _format_summary_html(self, summary: DailySummary) -> str:
        """Format summary as HTML email."""
        date_str = summary.date.strftime("%Y年%m月%d日")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1da1f2; border-bottom: 2px solid #1da1f2; padding-bottom: 10px; }}
        h2 {{ color: #14171a; margin-top: 30px; }}
        .stats {{ background: #f5f8fa; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .stats span {{ margin-right: 20px; }}
        .insight {{ background: #e8f5e9; padding: 10px 15px; margin: 10px 0; border-left: 4px solid #4caf50; border-radius: 4px; }}
        .analysis {{ white-space: pre-wrap; background: #fafafa; padding: 20px; border-radius: 8px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e1e8ed; color: #657786; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>📊 X/Twitter 每日监控报告</h1>
    <p><strong>日期：</strong>{date_str}</p>

    <div class="stats">
        <span>📱 监控账号: <strong>{summary.accounts_monitored}</strong></span>
        <span>📝 推文数量: <strong>{summary.total_tweets}</strong></span>
    </div>
"""

        if summary.key_insights:
            html += "<h2>🔑 关键洞察</h2>"
            for insight in summary.key_insights:
                html += f'<div class="insight">{insight}</div>'

        html += f"""
    <h2>📋 详细分析</h2>
    <div class="analysis">{summary.analysis}</div>

    <div class="footer">
        <p>本报告由 X-Monitor AI Agent 自动生成</p>
        <p>生成时间: {summary.generated_at.strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>
"""
        return html

    async def send_summary(self, summary: DailySummary) -> bool:
        """Send daily summary via email.

        Args:
            summary: The daily summary to send

        Returns:
            True if sent successfully, False otherwise
        """
        date_str = summary.date.strftime("%Y-%m-%d")
        subject = f"📊 X/Twitter 每日监控报告 - {date_str}"

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.username
        message["To"] = self.to_email

        # Plain text version
        text_content = f"""X/Twitter 每日监控报告 - {date_str}

监控账号: {summary.accounts_monitored}
推文数量: {summary.total_tweets}

{summary.analysis}

---
本报告由 X-Monitor AI Agent 自动生成
"""

        # HTML version
        html_content = self._format_summary_html(summary)

        message.attach(MIMEText(text_content, "plain", "utf-8"))
        message.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.username,
                password=self.password,
                start_tls=True,
            )
            logger.info(f"Email sent successfully to {self.to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

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
        """Format summary as HTML email using the same format as Markdown report."""
        date_str = summary.date.strftime("%Y年%m月%d日")
        gen_time = summary.generated_at.strftime("%Y-%m-%d %H:%M:%S")
        
        # Convert analysis text to HTML (preserve formatting)
        analysis_html = summary.analysis.replace("\n", "<br>\n")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            line-height: 1.8; 
            color: #333; 
            max-width: 900px; 
            margin: 0 auto; 
            padding: 30px 20px; 
            background: #f8f9fa;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{ 
            color: #1da1f2; 
            border-bottom: 3px solid #1da1f2; 
            padding-bottom: 15px; 
            margin-bottom: 25px;
            font-size: 28px;
        }}
        .meta {{ 
            background: #f5f8fa; 
            padding: 20px; 
            border-radius: 8px; 
            margin: 25px 0; 
            border-left: 4px solid #1da1f2;
        }}
        .meta p {{ 
            margin: 8px 0; 
            font-size: 15px;
        }}
        .meta strong {{ 
            color: #14171a;
            font-weight: 600;
        }}
        .divider {{
            border-top: 2px solid #e1e8ed;
            margin: 30px 0;
        }}
        .analysis {{ 
            white-space: pre-wrap; 
            background: #fafbfc; 
            padding: 25px; 
            border-radius: 8px; 
            line-height: 1.9;
            font-size: 15px;
            border: 1px solid #e1e8ed;
        }}
        .insights-section {{
            margin: 30px 0;
        }}
        .insights-section h2 {{
            color: #14171a;
            font-size: 22px;
            margin-bottom: 15px;
        }}
        .insight {{ 
            background: #e8f5e9; 
            padding: 12px 20px; 
            margin: 12px 0; 
            border-left: 4px solid #4caf50; 
            border-radius: 6px;
            font-size: 15px;
        }}
        .footer {{ 
            margin-top: 40px; 
            padding-top: 25px; 
            border-top: 2px solid #e1e8ed; 
            color: #657786; 
            text-align: center;
            font-size: 13px;
        }}
        .footer p {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 X/Twitter 每日监控报告</h1>
        
        <div class="meta">
            <p><strong>日期：</strong> {date_str}</p>
            <p><strong>监控账号：</strong> {summary.accounts_monitored} 个</p>
            <p><strong>推文数量：</strong> {summary.total_tweets} 条</p>
            <p><strong>生成时间：</strong> {gen_time}</p>
        </div>

        <div class="divider"></div>

        <div class="analysis">{analysis_html}</div>

        <div class="divider"></div>

        <div class="insights-section">
            <h2>关键洞察</h2>
"""

        if summary.key_insights:
            for i, insight in enumerate(summary.key_insights, 1):
                html += f'            <div class="insight">{i}. {insight}</div>\n'
        else:
            html += '            <div class="insight">（无关键洞察）</div>\n'

        html += f"""
        </div>

        <div class="divider"></div>

        <div class="footer">
            <p><em>本报告由 X-Monitor AI Agent 自动生成</em></p>
        </div>
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

        # Plain text version (same format as Markdown report)
        gen_time = summary.generated_at.strftime("%Y-%m-%d %H:%M:%S")
        date_display = summary.date.strftime("%Y年%m月%d日")
        
        text_content = f"""X/Twitter 每日监控报告

日期：{date_display}
监控账号：{summary.accounts_monitored} 个
推文数量：{summary.total_tweets} 条
生成时间：{gen_time}

---

{summary.analysis}

---

关键洞察
"""
        
        if summary.key_insights:
            for i, insight in enumerate(summary.key_insights, 1):
                text_content += f"{i}. {insight}\n"
        else:
            text_content += "（无关键洞察）\n"
        
        text_content += """
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

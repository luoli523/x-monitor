"""LLM-based tweet analyzer using OpenAI."""

from datetime import datetime
from loguru import logger
from openai import AsyncOpenAI

from src.models import Tweet, DailySummary


SYSTEM_PROMPT = """你是一个专业的社交媒体分析师，擅长分析推文内容并提供深度见解。
你的任务是：
1. 总结每个账号的主要动态
2. 识别重要话题和趋势
3. 分析观点和立场
4. 提供深度评论和洞察

请使用中文回复，保持专业、客观的分析风格。"""


class LLMAnalyzer:
    """Analyzer using OpenAI for tweet analysis."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        """Initialize the analyzer."""
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    def _format_tweets_for_analysis(self, tweets: list[Tweet]) -> str:
        """Format tweets into a string for LLM analysis."""
        if not tweets:
            return "没有推文数据。"

        # Group by author
        by_author: dict[str, list[Tweet]] = {}
        for tweet in tweets:
            if tweet.author_username not in by_author:
                by_author[tweet.author_username] = []
            by_author[tweet.author_username].append(tweet)

        lines = []
        for author, author_tweets in by_author.items():
            display_name = author_tweets[0].author_display_name or author
            lines.append(f"\n## @{author} ({display_name})")
            lines.append(f"共 {len(author_tweets)} 条推文\n")

            for tweet in author_tweets[:10]:  # Limit per author
                time_str = tweet.created_at.strftime("%Y-%m-%d %H:%M")
                engagement = f"❤️{tweet.likes} 🔁{tweet.retweets} 💬{tweet.replies}"

                prefix = ""
                if tweet.is_retweet:
                    prefix = "[转推] "
                elif tweet.is_reply:
                    prefix = "[回复] "

                lines.append(f"- [{time_str}] {prefix}{tweet.content[:200]}")
                lines.append(f"  {engagement}")
                lines.append(f"  {tweet.url}\n")

        return "\n".join(lines)

    async def analyze_tweets(self, tweets: list[Tweet], date: datetime) -> DailySummary:
        """Analyze tweets and generate daily summary.

        Args:
            tweets: List of tweets to analyze
            date: The date being summarized

        Returns:
            DailySummary with LLM-generated content
        """
        date_str = date.strftime("%Y年%m月%d日")
        formatted_tweets = self._format_tweets_for_analysis(tweets)

        # Get unique authors
        authors = set(t.author_username for t in tweets)

        user_prompt = f"""请分析以下 {date_str} 的推文数据，并提供：

1. **每日摘要**：简要总结每个账号的主要动态（2-3句话/账号）
2. **热点话题**：识别出现的主要话题和趋势
3. **深度分析**：分析这些推文反映的观点、立场和潜在影响
4. **关键洞察**：列出3-5条最重要的发现

推文数据：
{formatted_tweets}

请用结构化的格式输出分析结果。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )

            analysis_text = response.choices[0].message.content or ""
            logger.info(f"Generated analysis for {len(tweets)} tweets")

            # Extract key insights (simple extraction)
            key_insights = []
            if "关键洞察" in analysis_text or "关键发现" in analysis_text:
                lines = analysis_text.split("\n")
                in_insights = False
                for line in lines:
                    if "关键洞察" in line or "关键发现" in line:
                        in_insights = True
                        continue
                    if in_insights and line.strip().startswith(("-", "•", "1", "2", "3", "4", "5")):
                        insight = line.strip().lstrip("-•0123456789. ")
                        if insight:
                            key_insights.append(insight)
                    elif in_insights and line.strip() and not line.strip().startswith("#"):
                        if len(key_insights) >= 5:
                            break

            return DailySummary(
                date=date,
                accounts_monitored=len(authors),
                total_tweets=len(tweets),
                tweets=tweets,
                summary_text=analysis_text,
                analysis=analysis_text,
                key_insights=key_insights[:5],
            )

        except Exception as e:
            logger.error(f"Error analyzing tweets: {e}")
            return DailySummary(
                date=date,
                accounts_monitored=len(authors),
                total_tweets=len(tweets),
                tweets=tweets,
                summary_text=f"分析生成失败: {e}",
                analysis="",
            )

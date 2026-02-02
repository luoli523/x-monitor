"""LLM-based tweet analyzer using OpenAI."""

from datetime import datetime
from loguru import logger
from openai import AsyncOpenAI

from src.models import Tweet, DailySummary


SYSTEM_PROMPT = """你是一位资深的 AI 领域分析师和创业顾问，专注于以下领域：
- LLM/大模型技术学习与实践
- AI 工具和技术的最新探索
- AI 创业机会和商业模式
- 用 AI 赚钱的实战经验和方法

你的分析风格：
- 务实：关注可落地、可执行的内容
- 敏锐：捕捉潜在的商业机会和技术趋势
- 精炼：提炼最有价值的信息，不说废话
- 行动导向：给出具体的学习或行动建议

请使用中文回复。"""


class LLMAnalyzer:
    """Analyzer using OpenAI for tweet analysis."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        max_completion_tokens: int = 16000,
        temperature: float | None = None,
    ):
        """Initialize the analyzer.

        Args:
            api_key: OpenAI API key
            model: Model name to use
            max_completion_tokens: Maximum tokens for completion
            temperature: Temperature for sampling (None = model default)
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_completion_tokens = max_completion_tokens
        self.temperature = temperature

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

        user_prompt = f"""请分析以下 {date_str} 的推文数据，从 AI 学习者和创业者的视角提供深度分析：

## 分析维度

### 1. 🔥 今日必看（最重要，放在最前面）
从所有推文中精选 3-5 条最值得关注的内容，说明：
- 为什么值得关注
- 原文链接
- 建议的行动（学习/实践/收藏/深入研究）

### 2. 📚 LLM 学习与技术实践
- 有哪些关于大模型、Prompt 工程、Agent 开发的干货？
- 有什么新工具、新框架、新技术值得学习？
- 提取可以直接学习或复现的内容

### 3. 💡 AI 创业灵感
- 发现了哪些 AI 产品创意或商业机会？
- 有什么可以快速验证的 MVP 想法？
- 单人/小团队可以做的项目有哪些？

### 4. 💰 AI 赚钱实战
- 有哪些用 AI 赚钱的真实案例或方法？
- 有什么可复制的变现模式？
- 提取具体的数据和收益情况（如有）

### 5. 🎯 关键洞察
列出 3-5 条最重要的发现，每条包含：
- 洞察内容
- 信息来源（哪个账号）
- 为什么重要

### 6. 📋 账号动态速览
简要总结每个活跃账号今天发了什么（1-2句话/账号）

---

推文数据：
{formatted_tweets}

请确保分析具有可操作性，突出"今日必看"部分。"""

        try:
            # Build request kwargs
            request_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "max_completion_tokens": self.max_completion_tokens,
            }
            # Only add temperature if specified (some models don't support it)
            if self.temperature is not None:
                request_kwargs["temperature"] = self.temperature

            response = await self.client.chat.completions.create(**request_kwargs)

            analysis_text = response.choices[0].message.content or ""
            logger.info(f"Generated analysis for {len(tweets)} tweets")
            logger.debug(f"Raw response: {response}")
            logger.info(f"Analysis text length: {len(analysis_text)}")

            # Extract key insights (from "今日必看" or "关键洞察" sections)
            key_insights = []
            lines = analysis_text.split("\n")
            in_section = False
            section_keywords = ["今日必看", "关键洞察", "关键发现", "必看"]

            for line in lines:
                # Check if entering a key section
                if any(kw in line for kw in section_keywords):
                    in_section = True
                    continue
                # Check if leaving the section (new header)
                if in_section and line.strip().startswith("##"):
                    if len(key_insights) >= 3:  # Got enough from this section
                        in_section = False
                        continue
                # Extract insights
                if in_section and line.strip().startswith(("-", "•", "1", "2", "3", "4", "5", "*")):
                    insight = line.strip().lstrip("-•*0123456789. ")
                    if insight and len(insight) > 10:  # Filter out too short lines
                        key_insights.append(insight)
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

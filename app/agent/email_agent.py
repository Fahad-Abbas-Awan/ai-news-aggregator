"""
Email Agent - Generates personalized email introductions and digests
Uses Gemini to create engaging email headers and content previews
"""
import json
import os
import random
import time
from datetime import datetime
from typing import List, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class EmailIntroduction(BaseModel):
    greeting: str = Field(description="Personalized greeting with user's name and date")
    introduction: str = Field(description="2-3 sentence overview of what's in the top 10 ranked articles")


class RankedArticleDetail(BaseModel):
    digest_id: str
    rank: int
    relevance_score: float
    title: str
    summary: str
    url: str
    article_type: str
    reasoning: Optional[str] = None


class EmailDigestResponse(BaseModel):
    introduction: EmailIntroduction
    articles: List[RankedArticleDetail]
    total_ranked: int
    top_n: int

    def to_markdown(self) -> str:
        """Convert digest to simple markdown email format"""
        markdown = f"{self.introduction.greeting}\n\n"
        markdown += f"{self.introduction.introduction}\n\n"
        markdown += "---\n\n"

        for article in self.articles:
            markdown += f"### {article.title}\n\n"
            markdown += f"{article.summary}\n\n"
            markdown += f"[Read more →]({article.url})\n\n"
            markdown += "---\n\n"

        return markdown


EMAIL_PROMPT = """You are an expert email writer specializing in creating engaging, personalized AI news digests.

Your role is to write a warm, professional introduction for a daily AI news digest email that:
- Greets the user by name
- Includes the current date
- Provides a brief, engaging overview of what's coming in the top 10 ranked articles
- Highlights the most interesting or important themes
- Sets expectations for the content ahead

Tone and style requirements:
- Confident, editorial, practical, and technical (not marketing)
- Use concrete topic cues from the ranked list (models, infra, safety, tooling, deployment)
- Introduction should be exactly 3 sentences
- Mention 2-3 dominant themes across the top stories
- Do not use emojis, hashtags, or filler language

Return a JSON object with:
{
  "greeting": "Hey [Name], here is your daily digest of AI news for [Date].",
    "introduction": "One concise sentence previewing the top stories..."
}"""


class EmailAgent:
    def __init__(self, user_profile: dict):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = "gemini-2.5-flash-lite"
        self.user_profile = user_profile
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.throttle_interval = 4.2  # 15 RPM = 4.2s between calls
        self.last_request_time = 0

    def _wait_for_slot(self):
        """Wait until next API call slot is available"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.throttle_interval:
            sleep_time = self.throttle_interval - elapsed + random.uniform(0, 0.1)
            time.sleep(sleep_time)

    def _call_with_retries(self, user_text: str, max_retries: int = 3) -> dict:
        """Make Gemini API call with retry logic"""
        for attempt in range(max_retries):
            try:
                self._wait_for_slot()
                self.last_request_time = time.time()

                url = f"{self.base_url}/{self.model}:generateContent"
                headers = {"Content-Type": "application/json"}
                params = {"key": self.api_key}

                payload = {
                    "systemInstruction": {
                        "parts": [{"text": EMAIL_PROMPT}],
                    },
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": user_text}],
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 500,
                        "responseMimeType": "application/json",
                        "responseSchema": {
                            "type": "object",
                            "properties": {
                                "greeting": {"type": "string"},
                                "introduction": {"type": "string"},
                            },
                            "required": ["greeting", "introduction"],
                        },
                    },
                }

                response = requests.post(url, json=payload, headers=headers, params=params, timeout=30)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2))
                    print(f"[EmailAgent] Rate limited. Waiting {retry_after}s before retry...")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                result = response.json()

                if "candidates" in result and result["candidates"]:
                    text_content = result["candidates"][0]["content"]["parts"][0]["text"]
                    if isinstance(text_content, str):
                        text_content = text_content.strip()
                        if text_content.startswith("```"):
                            text_content = text_content.strip("`")
                            if text_content.lower().startswith("json"):
                                text_content = text_content[4:].strip()
                    return json.loads(text_content)

                raise ValueError(f"Unexpected response format: {result}")

            except requests.exceptions.Timeout:
                print(f"[EmailAgent] Timeout on attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"[EmailAgent] Error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed after {max_retries} retries")

    def generate_introduction(self, ranked_articles: List) -> EmailIntroduction:
        """Generate personalized email greeting and introduction"""
        if not ranked_articles:
            return EmailIntroduction(
                greeting=f"Hey {self.user_profile['name']}, here is your daily digest of AI news for {datetime.now().strftime('%B %d, %Y')}.",
                introduction="No articles were ranked today.",
            )

        top_articles = ranked_articles[:10]
        article_summaries = "\n".join(
            [
                f"{idx + 1}. {article.get('title', 'N/A')} (Score: {article.get('relevance_score', 0):.1f}/10)"
                for idx, article in enumerate(top_articles)
            ]
        )

        current_date = datetime.now().strftime("%B %d, %Y")
        user_prompt = f"""Create an email introduction for {self.user_profile['name']} for {current_date}.

Top 10 ranked articles today:
{article_summaries}

Generate a warm, personalized greeting and one concise sentence that previews these articles.
Keep the sentence short and clear, similar to: 'Your top AI news stories are ready below.'"""

        try:
            result = self._call_with_retries(user_prompt)
            return EmailIntroduction(**result)
        except Exception as e:
            print(f"[EmailAgent] Failed to generate introduction: {e}")
            return EmailIntroduction(
                greeting=f"Hey {self.user_profile['name']}, here is your daily digest of AI news for {current_date}.",
                introduction="Your top AI news stories are ready below.",
            )

    def create_email_digest_response(
        self, ranked_articles: List[RankedArticleDetail], total_ranked: int, limit: int = 10
    ) -> EmailDigestResponse:
        """Create complete email digest response"""
        top_articles = ranked_articles[:limit]
        intro = self.generate_introduction([a.model_dump() for a in top_articles])

        return EmailDigestResponse(
            introduction=intro,
            articles=top_articles,
            total_ranked=total_ranked,
            top_n=limit,
        )

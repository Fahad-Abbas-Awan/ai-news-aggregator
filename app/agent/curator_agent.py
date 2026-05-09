import json
import os
import random
import time
from typing import List, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class RankedArticle(BaseModel):
    digest_id: str = Field(description="The ID of the digest (article_type:article_id)")
    relevance_score: float = Field(description="Relevance score from 0.0 to 10.0", ge=0.0, le=10.0)
    rank: int = Field(description="Rank position (1 = most relevant)", ge=1)
    reasoning: str = Field(description="Brief explanation of why this article is ranked here")


class RankedDigestList(BaseModel):
    articles: List[RankedArticle] = Field(description="List of ranked articles")


CURATOR_PROMPT = """You are an Assignment Editor Agent for an AI news desk.

Your job is to rank the latest AI news digests for a specific user profile.
Read the user profile carefully and score each digest by relevance, usefulness, depth, novelty, and practical value.
Prioritize practical engineering value over general AI headlines.
Do not reward marketing language unless it includes concrete technical substance.

Ranking criteria:
1. Relevance to the user's background and stated interests
2. Technical depth and practical utility
3. Novelty and significance
4. Alignment with the user's expertise level
5. Actionability and real-world applicability

Scoring guide:
- 9.0-10.0: Must-read, directly aligned with the user profile
- 7.0-8.9: Very relevant, strong match
- 5.0-6.9: Moderately relevant
- 3.0-4.9: Somewhat relevant
- 0.0-2.9: Low relevance

Reasoning rules:
- 1-2 sentences only
- Mention at least one profile alignment signal (interests, expertise, or preferences)
- Be concrete and avoid vague phrases like "highly relevant" without evidence

Return a strictly structured JSON object with an "articles" array. Each item must include digest_id, relevance_score, rank, and reasoning. Ranks must be unique and ordered from most relevant to least relevant."""


class CuratorAgent:
    def __init__(self, user_profile: dict):
        self.api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip()
        self.model = os.getenv("GEMINI_CURATOR_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"))
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.user_profile = user_profile
        self.system_prompt = self._build_system_prompt()
        self._min_interval = float(os.getenv("GEMINI_MIN_INTERVAL", "4.2"))
        self._last_request_time = 0.0
        self._max_attempts = int(os.getenv("GEMINI_MAX_ATTEMPTS", "5"))

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set")

    def _build_system_prompt(self) -> str:
        interests = "\n".join(f"- {interest}" for interest in self.user_profile["interests"])
        preferences = self.user_profile["preferences"]
        pref_text = "\n".join(f"- {key}: {value}" for key, value in preferences.items())

        return f"""{CURATOR_PROMPT}

User Profile:
Name: {self.user_profile['name']}
Title: {self.user_profile['title']}
Background: {self.user_profile['background']}
Expertise Level: {self.user_profile['expertise_level']}

Interests:
{interests}

Preferences:
{pref_text}"""

    def _wait_for_slot(self) -> None:
        now = time.time()
        delta = now - self._last_request_time
        if delta < self._min_interval:
            time.sleep(self._min_interval - delta)
        self._last_request_time = time.time()

    def _call_with_retries(self, payload: dict) -> Optional[dict]:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        for attempt in range(1, self._max_attempts + 1):
            try:
                self._wait_for_slot()
                response = requests.post(
                    url,
                    params={"key": self.api_key},
                    json=payload,
                    timeout=60,
                )
                if response.status_code == 200:
                    return response.json()

                if response.status_code in (429, 502, 503, 504) or 500 <= response.status_code < 600:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = float(retry_after)
                        except Exception:
                            wait = min(60.0, 2 ** attempt)
                    else:
                        wait = min(60.0, (2 ** (attempt - 1)) + random.random())
                    time.sleep(wait)
                    continue

                response.raise_for_status()
            except requests.RequestException:
                wait = min(60.0, (2 ** (attempt - 1)) + random.random())
                time.sleep(wait)
                continue

        return None

    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:
        if not digests:
            return []

        digest_list = "\n\n".join(
            [
                f"ID: {digest['id']}\nTitle: {digest['title']}\nSummary: {digest['summary']}\nType: {digest['article_type']}"
                for digest in digests
            ]
        )

        user_prompt = f"""Rank these {len(digests)} AI news digests based on the user profile.

{digest_list}

Provide a relevance score (0.0-10.0) and rank (1-{len(digests)}) for each article, ordered from most to least relevant.
Return only valid JSON in the following shape:
{{
  "articles": [
    {{
      "digest_id": "article_type:article_id",
      "relevance_score": 9.5,
      "rank": 1,
      "reasoning": "brief explanation"
    }}
  ]
}}"""

        payload = {
            "systemInstruction": {
                "parts": [{"text": self.system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }

        try:
            data = self._call_with_retries(payload)
            if not data:
                return []

            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            if not text:
                return []

            parsed = json.loads(text) if isinstance(text, str) else text
            ranked_list = RankedDigestList.model_validate(parsed)
            return ranked_list.articles
        except Exception as exc:
            print(f"Error ranking digests: {exc}")
            return []

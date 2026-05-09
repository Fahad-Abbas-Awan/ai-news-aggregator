import json
import os
import time
import random
from typing import Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel


load_dotenv()


class DigestOutput(BaseModel):
    title: str
    summary: str


class DigestAgent:
    def __init__(self):
        self.api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.system_prompt = (
            "You are a senior AI news editor writing a daily digest for technical readers. "
            "Use factual, specific language and avoid hype. "
            "Create a clear title (8-14 words) and a compact summary (exactly 3 sentences). "
            "Sentence 1: what happened (company/model/product and concrete detail). "
            "Sentence 2: why it matters for AI builders in practice. "
            "Sentence 3: key implication, risk, or what to watch next. "
            "Do not invent facts beyond the source content. "
            "Return only valid JSON with keys 'title' and 'summary'."
        )

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set")

        # Throttle configuration (safe defaults for gemini-2.5-flash-lite)
        # Gemini free-tier ~15 requests/min => ~4s interval
        self._min_interval = float(os.getenv("GEMINI_MIN_INTERVAL", "4.2"))
        self._last_request_time = 0.0
        self._max_attempts = int(os.getenv("GEMINI_MAX_ATTEMPTS", "5"))
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
                resp = requests.post(
                    url, params={"key": self.api_key}, json=payload, timeout=60
                )
                if resp.status_code == 200:
                    return resp.json()

                # Handle retryable errors
                if resp.status_code in (429, 502, 503, 504) or 500 <= resp.status_code < 600:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = float(retry_after)
                        except Exception:
                            wait = min(60.0, 2 ** attempt)
                    else:
                        # exponential backoff with jitter
                        wait = min(60.0, (2 ** (attempt - 1)) + random.random())
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
            except requests.RequestException as exc:
                # network-level error, backoff and retry
                wait = min(60.0, (2 ** (attempt - 1)) + random.random())
                time.sleep(wait)
                continue

        return None

    def generate_digest(self, title: str, content: str, article_type: str) -> Optional[DigestOutput]:
        # Limit content length to keep token usage reasonable
        safe_content = content[:8000]
        user_prompt = (
            f"Create a digest for this {article_type} item.\n"
            f"Original title: {title}\n"
            f"Content:\n{safe_content}"
        )

        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": self.system_prompt,
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": user_prompt,
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "responseMimeType": "application/json",
            },
        }

        try:
            data = self._call_with_retries(payload)
            if not data:
                return None
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            if not text:
                return None

            if isinstance(text, str):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return None
            else:
                parsed = text

            return DigestOutput.model_validate(parsed)
        except Exception as exc:
            print(f"Error generating digest: {exc}")
            return None
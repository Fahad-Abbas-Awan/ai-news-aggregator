from datetime import datetime, timedelta, timezone
from typing import List, Optional

import feedparser
from docling.document_converter import DocumentConverter
from pydantic import BaseModel


class OpenAIArticle(BaseModel):
    title: str
    description: str
    url: str
    guid: str
    published_at: datetime
    category: Optional[str] = None


class OpenAIScraper:
    def __init__(self):
        self.rss_url = "https://openai.com/news/rss.xml"
        self.converter = DocumentConverter()

    def get_rss_url(self) -> str:
        return self.rss_url

    def get_articles(self, hours: int = 200) -> List[OpenAIArticle]:
        feed = feedparser.parse(self.get_rss_url())

        if not feed.entries:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        articles: List[OpenAIArticle] = []

        for entry in feed.entries:
            published_parsed = getattr(entry, "published_parsed", None)
            if not published_parsed:
                continue

            published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
            if published_time < cutoff_time:
                continue

            articles.append(
                OpenAIArticle(
                    title=entry.get("title", ""),
                    description=entry.get("summary", entry.get("description", "")),
                    url=entry.get("link", ""),
                    guid=entry.get("id", entry.get("link", "")),
                    published_at=published_time,
                    category=(
                        entry.get("tags", [{}])[0].get("term")
                        if entry.get("tags")
                        else None
                    ),
                )
            )

        return articles


_default_scraper = OpenAIScraper()


def get_rss_url() -> str:
    return _default_scraper.get_rss_url()


def get_articles(hours: int = 200) -> List[OpenAIArticle]:
    return _default_scraper.get_articles(hours)


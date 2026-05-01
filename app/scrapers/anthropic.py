from datetime import datetime, timedelta, timezone
from typing import List, Optional

import feedparser
from docling.document_converter import DocumentConverter
from pydantic import BaseModel


RSS_URLS = [
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
]


class AnthropicArticle(BaseModel):
    title: str
    description: str
    url: str
    guid: str
    published_at: datetime
    category: Optional[str] = None
    markdown: Optional[str] = None


class AnthropicScraper:
    def __init__(self):
        self.rss_urls = RSS_URLS
        self.converter = DocumentConverter()

    def get_articles(self, hours: int = 200, fetch_markdown: bool = False) -> List[AnthropicArticle]:
        """Fetch and return recent articles from all Anthropic RSS feeds.

        - `hours`: time window to include (default 200).
        - `fetch_markdown`: when True, attempt to fetch full article markdown via Docling.
        """
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        articles: List[AnthropicArticle] = []
        seen_guids = set()

        for rss_url in self.rss_urls:
            feed = feedparser.parse(rss_url)
            if not getattr(feed, "entries", None):
                continue

            for entry in feed.entries:
                published_parsed = getattr(entry, "published_parsed", None)
                if not published_parsed:
                    continue

                published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                if published_time < cutoff_time:
                    continue

                guid = entry.get("id", entry.get("link", "")) or entry.get("link", "")
                if guid in seen_guids:
                    continue
                seen_guids.add(guid)

                markdown = None
                if fetch_markdown:
                    markdown = self.url_to_markdown(entry.get("link", ""))

                articles.append(
                    AnthropicArticle(
                        title=entry.get("title", ""),
                        description=entry.get("summary", entry.get("description", "")),
                        url=entry.get("link", ""),
                        guid=guid,
                        published_at=published_time,
                        category=(entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None),
                        markdown=markdown,
                    )
                )

        # Sort newest first
        articles.sort(key=lambda a: a.published_at, reverse=True)
        return articles

    def url_to_markdown(self, url: str) -> Optional[str]:
        """Use Docling's DocumentConverter to convert a URL to markdown. Returns None on failure."""
        if not url:
            return None
        try:
            result = self.converter.convert(url)
            return result.document.export_to_markdown()
        except Exception:
            return None


_default_scraper = AnthropicScraper()


def get_articles(hours: int = 200) -> List[AnthropicArticle]:
    return _default_scraper.get_articles(hours)

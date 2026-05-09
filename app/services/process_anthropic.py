from typing import Optional

from app.scrapers.anthropic import AnthropicScraper
from app.database.repository import NewsRepository


def process_anthropic_markdown(limit: Optional[int] = None) -> dict:
    scraper = AnthropicScraper()
    repo = NewsRepository()

    articles = repo.get_anthropic_articles_without_markdown(limit=limit)
    processed = 0
    failed = 0

    try:
        for article in articles:
            markdown = scraper.url_to_markdown(article.url)
            try:
                if markdown:
                    repo.update_anthropic_article_markdown(article.guid, markdown)
                    processed += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
                continue

        return {
            "total": len(articles),
            "processed": processed,
            "failed": failed,
        }
    finally:
        repo.close()
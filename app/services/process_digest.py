from typing import Optional
import logging

from app.agent.digest_agent import DigestAgent
from app.database.repository import NewsRepository


logger = logging.getLogger(__name__)


def process_digests(limit: Optional[int] = None) -> dict:
    agent = DigestAgent()
    repo = NewsRepository()

    articles = repo.get_articles_without_digest(limit=limit)
    processed = 0
    failed = 0
    total = len(articles)

    logger.info("Starting digest processing for %s items", total)

    try:
        for index, article in enumerate(articles, start=1):
            title_preview = article["title"][:80].replace("\n", " ")
            logger.info(
                "[%s/%s] Processing %s | id=%s | title=%s",
                index,
                total,
                article["type"],
                article["id"],
                title_preview,
            )

            digest_result = agent.generate_digest(
                title=article["title"],
                content=article["content"],
                article_type=article["type"],
            )

            if digest_result:
                repo.create_digest(
                    article_type=article["type"],
                    article_id=article["id"],
                    url=article["url"],
                    title=digest_result.title,
                    summary=digest_result.summary,
                    published_at=article.get("published_at"),
                )
                processed += 1
                logger.info("[%s/%s] Created digest successfully", index, total)
            else:
                failed += 1
                logger.warning("[%s/%s] Failed to create digest", index, total)

        logger.info(
            "Digest processing finished | total=%s processed=%s failed=%s",
            total,
            processed,
            failed,
        )

        return {
            "total": total,
            "processed": processed,
            "failed": failed,
        }
    finally:
        repo.close()
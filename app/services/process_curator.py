import logging
from typing import Optional

from app.agent.curator_agent import CuratorAgent
from app.database.repository import NewsRepository
from app.profiles.user_profile import USER_PROFILE

logger = logging.getLogger(__name__)


def curate_digests(hours: int = 24) -> dict:
    curator = CuratorAgent(USER_PROFILE)
    repo = NewsRepository()

    digests = repo.get_recent_digests(hours=hours)
    total = len(digests)

    if total == 0:
        logger.warning("No digests found from the last %s hours", hours)
        return {"total": 0, "ranked": 0, "articles": []}

    logger.info("Curating %s digests from the last %s hours", total, hours)
    logger.info("User profile: %s - %s", USER_PROFILE["name"], USER_PROFILE["background"])

    ranked_articles = curator.rank_digests(digests)

    if not ranked_articles:
        logger.error("Failed to rank digests")
        return {"total": total, "ranked": 0, "articles": []}

    ranked_articles = sorted(ranked_articles, key=lambda item: item.rank)

    logger.info("Successfully ranked %s articles", len(ranked_articles))
    logger.info("\n=== Top 10 Ranked Articles ===")

    for article in ranked_articles[:10]:
        digest = next((digest for digest in digests if digest["id"] == article.digest_id), None)
        if digest:
            logger.info("\nRank %s | Score: %.1f/10.0", article.rank, article.relevance_score)
            logger.info("Title: %s", digest["title"])
            logger.info("Type: %s", digest["article_type"])
            logger.info("Reasoning: %s", article.reasoning)

    return {
        "total": total,
        "ranked": len(ranked_articles),
        "articles": [
            {
                "digest_id": article.digest_id,
                "rank": article.rank,
                "relevance_score": article.relevance_score,
                "reasoning": article.reasoning,
            }
            for article in ranked_articles
        ],
    }

import logging
from datetime import datetime

from app.database.connection import engine
from app.database.models import Base
from app.runner import run_scrapers
from app.services.process_anthropic import process_anthropic_markdown
from app.services.process_youtube import process_youtube_transcripts
from app.services.process_digest import process_digests
from app.services.process_curator import curate_digests
from app.services.process_email import send_digest_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_daily_pipeline(hours: int = 24) -> dict:
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Starting Daily AI News Aggregator Pipeline")
    logger.info("=" * 60)

    results = {
        "start_time": start_time.isoformat(),
        "scraping": {},
        "processing": {},
        "digests": {},
        "curation": {},
        "email": {},
        "success": False,
    }

    try:
        logger.info("\n[0/6] Ensuring database tables exist...")
        try:
            with engine.connect():
                Base.metadata.create_all(engine)
                logger.info("✓ Database tables verified/created")
        except Exception as exc:
            logger.error("Failed to create database tables: %s", exc)
            raise

        logger.info("\n[1/6] Scraping articles from sources...")
        scraping_results = run_scrapers(hours=hours)
        results["scraping"] = {
            "youtube": len(scraping_results.get("youtube", [])),
            "openai": len(scraping_results.get("openai", [])),
            "anthropic": len(scraping_results.get("anthropic", [])),
        }
        logger.info(
            "✓ Scraped %s YouTube videos, %s OpenAI articles, %s Anthropic articles",
            results["scraping"]["youtube"],
            results["scraping"]["openai"],
            results["scraping"]["anthropic"],
        )

        logger.info("\n[2/6] Processing Anthropic markdown...")
        anthropic_result = process_anthropic_markdown()
        results["processing"]["anthropic"] = anthropic_result
        logger.info(
            "✓ Processed %s Anthropic articles (%s failed)",
            anthropic_result["processed"],
            anthropic_result["failed"],
        )

        logger.info("\n[3/6] Processing YouTube transcripts...")
        youtube_result = process_youtube_transcripts()
        results["processing"]["youtube"] = youtube_result
        logger.info(
            "✓ Processed %s transcripts (%s unavailable)",
            youtube_result["processed"],
            youtube_result["unavailable"],
        )

        logger.info("\n[4/6] Creating digests for articles...")
        digest_result = process_digests()
        results["digests"] = digest_result
        logger.info(
            "✓ Created %s digests (%s failed out of %s total)",
            digest_result["processed"],
            digest_result["failed"],
            digest_result["total"],
        )

        logger.info("\n[5/6] Curating last 24 hours of digests...")
        curation_result = curate_digests(hours=hours)
        results["curation"] = curation_result
        if curation_result.get("ranked", 0) > 0:
            logger.info("✓ Ranked %s digests", curation_result["ranked"])
        else:
            logger.error("✗ Failed to rank digests")

        logger.info("\n[6/6] Sending email digest...")
        email_result = send_digest_email(hours=hours, top_n=10)
        results["email"] = email_result
        if email_result.get("success"):
            logger.info("✓ Email sent successfully!")
            results["success"] = True
        else:
            logger.error("✗ Failed to send email: %s", email_result.get("error", "Unknown error"))

    except Exception as exc:
        logger.error("Pipeline failed with error: %s", exc, exc_info=True)
        results["error"] = str(exc)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    results["end_time"] = end_time.isoformat()
    results["duration_seconds"] = duration

    logger.info("\n" + "=" * 60)
    logger.info("Pipeline Summary")
    logger.info("=" * 60)
    logger.info("Duration: %.1f seconds", duration)
    logger.info("Scraped: %s", results["scraping"])
    logger.info("Processed: %s", results["processing"])
    logger.info("Digests: %s", results["digests"])
    logger.info("Curation: %s", results["curation"])
    logger.info("Email: %s", results["email"])
    logger.info("Success: %s", results["success"])
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    result = run_daily_pipeline(hours=24)
    raise SystemExit(0 if result["success"] else 1)

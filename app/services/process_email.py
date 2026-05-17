"""
Process Email - Orchestrates email digest generation and sending
"""
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Allow direct execution: python app/services/process_email.py
if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

load_dotenv()

from app.agent.email_agent import EmailAgent, RankedArticleDetail, EmailDigestResponse
from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import USER_PROFILE
from app.database.repository import NewsRepository
from app.services.email import send_email, digest_to_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def generate_email_digest(hours: int = 24, top_n: int = 10) -> EmailDigestResponse:
    """Generate email digest with ranking and introduction"""
    curator = CuratorAgent(USER_PROFILE)
    email_agent = EmailAgent(USER_PROFILE)
    repo = NewsRepository()

    digests = repo.get_recent_digests(hours=hours)
    total = len(digests)

    if total == 0:
        logger.warning("No digests found from the last %s hours", hours)
        intro = email_agent.generate_introduction([])
        return EmailDigestResponse(
            introduction=intro,
            articles=[],
            total_ranked=0,
            top_n=top_n,
        )

    logger.info(f"Ranking {total} digests for email generation")
    ranked_articles = curator.rank_digests(digests)

    if not ranked_articles:
        logger.error("Failed to rank digests")
        raise ValueError("Failed to rank articles")

    logger.info(f"Generating email digest with top {top_n} articles")

    # Build article details from ranked articles and digests
    article_details = []
    for a in ranked_articles:
        digest = next((d for d in digests if d["id"] == a.digest_id), None)
        if digest:
            article_details.append(
                RankedArticleDetail(
                    digest_id=a.digest_id,
                    rank=a.rank,
                    relevance_score=a.relevance_score,
                    reasoning=a.reasoning,
                    title=digest.get("title", ""),
                    summary=digest.get("summary", ""),
                    url=digest.get("url", ""),
                    article_type=digest.get("article_type", ""),
                )
            )

    email_digest = email_agent.create_email_digest_response(
        ranked_articles=article_details, total_ranked=len(ranked_articles), limit=top_n
    )

    logger.info("Email digest generated successfully")
    logger.info(f"\n=== Email Introduction ===")
    logger.info(email_digest.introduction.greeting)
    logger.info(f"\n{email_digest.introduction.introduction}")
    logger.info(f"\nTop {top_n} articles prepared for sending")

    return email_digest


def send_digest_email(hours: int = 24, top_n: int = 10) -> dict:
    """Generate and send email digest"""
    try:
        result = generate_email_digest(hours=hours, top_n=top_n)

        if not result.articles:
            logger.warning("No digests available; skipping email send")
            return {
                "success": True,
                "skipped": True,
                "reason": f"No digests found in last {hours} hours",
                "articles_count": 0,
            }

        markdown_content = result.to_markdown()
        html_content = digest_to_html(result)

        # Extract date from greeting
        date_str = result.introduction.greeting.split("for ")[-1].rstrip(".")
        subject = f"Daily AI News Digest - {date_str}"

        logger.info(f"\nSending email to {USER_PROFILE['name']}...")
        send_email(subject=subject, body_text=markdown_content, body_html=html_content)

        logger.info("✅ Email sent successfully!")
        return {
            "success": True,
            "skipped": False,
            "subject": subject,
            "articles_count": len(result.articles),
            "message": f"Email sent with {len(result.articles)} top articles",
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    result = send_digest_email(hours=24, top_n=10)
    if result["success"]:
        print("\n" + "=" * 60)
        print("✅ EMAIL SENT SUCCESSFULLY")
        print("=" * 60)
        print(f"Subject: {result['subject']}")
        print(f"Articles: {result['articles_count']}")
    else:
        print(f"\n❌ Failed: {result['error']}")

"""
Temporary script to delete all data from the database tables.
WARNING: This will permanently delete all records.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.create_tables import create_tables
from app.database.connection import get_session
from app.database.models import Digest, YouTubeVideo, OpenAIArticle, AnthropicArticle


def clear_database() -> None:
    create_tables()
    session = get_session()
    try:
        # Delete all records from each table
        youtube_count = session.query(YouTubeVideo).delete()
        openai_count = session.query(OpenAIArticle).delete()
        anthropic_count = session.query(AnthropicArticle).delete()
        digest_count = session.query(Digest).delete()
        session.commit()

        print(f"Deleted {youtube_count} YouTube videos")
        print(f"Deleted {openai_count} OpenAI articles")
        print(f"Deleted {anthropic_count} Anthropic articles")
        print(f"Deleted {digest_count} digests")
        print("\nDatabase cleared successfully!")
    except Exception as e:
        session.rollback()
        print(f"Error clearing database: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    confirm = input("⚠️  WARNING: This will delete ALL data from the database. Continue? (y/N): ")
    if confirm.lower() == "y":
        clear_database()
    else:
        print("Aborted.")

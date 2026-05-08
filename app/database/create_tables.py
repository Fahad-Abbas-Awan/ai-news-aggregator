import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.connection import engine
from app.database.models import Base
from sqlalchemy import text


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)

    # Ensure `markdown` column exists on `anthropic_articles` for deployments
    # where the table was created before the model included `markdown`.
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS anthropic_articles ADD COLUMN IF NOT EXISTS markdown TEXT"
                )
            )
            conn.commit()
    except Exception:
        # Best-effort: do not raise for existing deployments, user can run migrations manually.
        pass


if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully.")

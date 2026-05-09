from app.database.create_tables import create_tables
from app.daily_runner import run_daily_pipeline


def main(hours: int = 10):
    create_tables()
    return run_daily_pipeline(hours=hours)


if __name__ == "__main__":
    main(hours=24)
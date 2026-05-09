from typing import Any

from app.database.repository import NewsRepository
from app.scrapers.youtube import YouTubeScraper
from app.scrapers.openai import OpenAIScraper
from app.scrapers.anthropic import AnthropicScraper
from app.config import YOUTUBE_CHANNELS


def run_scrapers(hours: int = 200) -> dict[str, Any]:
    """
    Run all three scrapers and return results.
    
    - `hours`: time window to fetch (default 200 hours)
    
    Returns a dict with keys: 'youtube', 'openai', 'anthropic', 'saved'
    """
    results = {
        "youtube": [],
        "openai": [],
        "anthropic": [],
        "saved": {
            "youtube": 0,
            "openai": 0,
            "anthropic": 0,
        },
    }

    repository = NewsRepository()

    try:
        # Scrape YouTube channels and save the base video data first.
        # Transcript enrichment happens in a separate processing step.
        youtube_scraper = YouTubeScraper()
        for channel_id in YOUTUBE_CHANNELS:
            videos = youtube_scraper.get_latest_videos(channel_id, hours=hours)
            results["youtube"].extend(videos)
            results["saved"]["youtube"] += repository.save_youtube_videos(channel_id, videos)

        # Scrape OpenAI and save
        openai_scraper = OpenAIScraper()
        openai_articles = openai_scraper.get_articles(hours=hours)
        results["openai"].extend(openai_articles)
        results["saved"]["openai"] = repository.save_openai_articles(openai_articles)

        # Scrape Anthropic and save without markdown; it will be enriched in a separate processing step
        anthropic_scraper = AnthropicScraper()
        anthropic_articles = anthropic_scraper.get_articles(hours=hours, fetch_markdown=False)
        results["anthropic"].extend(anthropic_articles)
        results["saved"]["anthropic"] = repository.save_anthropic_articles(anthropic_articles)
    finally:
        repository.close()

    return results

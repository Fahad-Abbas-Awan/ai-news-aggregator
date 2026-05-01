from typing import List, Dict

from app.scrapers.youtube import YouTubeScraper, ChannelVideo
from app.scrapers.openai import OpenAIScraper, OpenAIArticle
from app.scrapers.anthropic import AnthropicScraper, AnthropicArticle
from app.services.config import YOUTUBE_CHANNELS


def run_scrapers(hours: int = 200) -> Dict[str, List]:
    """
    Run all three scrapers and return results.
    
    - `hours`: time window to fetch (default 200 hours)
    
    Returns a dict with keys: 'youtube', 'openai', 'anthropic'
    """
    results = {
        "youtube": [],
        "openai": [],
        "anthropic": [],
    }

    # Scrape YouTube channels (with transcripts)
    youtube_scraper = YouTubeScraper()
    for channel_id in YOUTUBE_CHANNELS:
        videos = youtube_scraper.scrape_channel(channel_id, hours=hours)
        results["youtube"].extend(videos)

    # Scrape OpenAI
    openai_scraper = OpenAIScraper()
    articles = openai_scraper.get_articles(hours=hours)
    results["openai"].extend(articles)

    # Scrape Anthropic
    anthropic_scraper = AnthropicScraper()
    articles = anthropic_scraper.get_articles(hours=hours)
    results["anthropic"].extend(articles)

    return results

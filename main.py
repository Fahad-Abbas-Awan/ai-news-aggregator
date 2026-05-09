from app.database.create_tables import create_tables
from app.runner import run_scrapers
from app.services.process_digest import process_digests
from app.services.process_anthropic import process_anthropic_markdown
from app.services.process_youtube import process_youtube_transcripts


def main(hours: int = 200):
    create_tables()
    results = run_scrapers(hours=hours)

    anthropic_result = process_anthropic_markdown()
    youtube_result = process_youtube_transcripts()
    digest_result = process_digests()
    
    print(f"\n=== Scraping Results (last {hours} hours) ===")
    print(f"YouTube videos: {len(results['youtube'])}")
    print(f"Saved YouTube videos: {results['saved']['youtube']}")
    print(f"OpenAI articles: {len(results['openai'])}")
    print(f"Saved OpenAI articles: {results['saved']['openai']}")
    print(f"Anthropic articles: {len(results['anthropic'])}")
    print(f"Saved Anthropic articles: {results['saved']['anthropic']}")
    print(f"Anthropic markdown processed: {anthropic_result['processed']}")
    print(f"Anthropic markdown failed: {anthropic_result['failed']}")
    print(f"YouTube transcripts processed: {youtube_result['processed']}")
    print(f"YouTube transcripts unavailable: {youtube_result['unavailable']}")
    print(f"Digest articles processed: {digest_result['processed']}")
    print(f"Digest articles failed: {digest_result['failed']}")
    
    return results


if __name__ == "__main__":
    main(hours=24)
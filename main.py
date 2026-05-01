from app.services.runner import run_scrapers


def main(hours: int = 200):
    results = run_scrapers(hours=hours)
    
    print(f"\n=== Scraping Results (last {hours} hours) ===")
    print(f"YouTube videos: {len(results['youtube'])}")
    print(f"OpenAI articles: {len(results['openai'])}")
    print(f"Anthropic articles: {len(results['anthropic'])}")
    
    return results


if __name__ == "__main__":
    main(hours=200)
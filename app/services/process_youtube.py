from typing import Optional

from app.database.repository import NewsRepository
from app.scrapers.youtube import YouTubeScraper


TRANSCRIPT_UNAVAILABLE_MARKER = "__UNAVAILABLE__"


def process_youtube_transcripts(limit: Optional[int] = None) -> dict:
    scraper = YouTubeScraper()
    repo = NewsRepository()

    videos = repo.get_youtube_videos_without_transcript(limit=limit)
    processed = 0
    unavailable = 0
    failed = 0

    try:
        for video in videos:
            try:
                transcript_result = scraper.get_transcript(video.video_id)
                if transcript_result:
                    repo.update_youtube_video_transcript(video.video_id, transcript_result.text)
                    processed += 1
                else:
                    repo.update_youtube_video_transcript(video.video_id, TRANSCRIPT_UNAVAILABLE_MARKER)
                    unavailable += 1
            except Exception:
                repo.update_youtube_video_transcript(video.video_id, TRANSCRIPT_UNAVAILABLE_MARKER)
                unavailable += 1

        return {
            "total": len(videos),
            "processed": processed,
            "unavailable": unavailable,
            "failed": failed,
        }
    finally:
        repo.close()
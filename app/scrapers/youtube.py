from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
from app.services.youtube import get_transcript


def get_rss_url(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def extract_video_id(video_url: str) -> str:
    if "youtube.com/watch?v=" in video_url:
        return video_url.split("v=")[1].split("&")[0]
    if "youtube.com/shorts/" in video_url:
        return video_url.split("shorts/")[1].split("?")[0]
    if "youtu.be/" in video_url:
        return video_url.split("youtu.be/")[1].split("?")[0]
    return video_url


def get_latest_videos(channel_id: str, hours: int = 24) -> list[dict]:
    feed = feedparser.parse(get_rss_url(channel_id))

    if not feed.entries:
        return []

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    videos = []

    for entry in feed.entries:
        if "/shorts/" in entry.link:
            continue

        published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if published_time >= cutoff_time:
            video_id = extract_video_id(entry.link)
            videos.append(
                {
                    "title": entry.title,
                    "url": entry.link,
                    "video_id": video_id,
                    "published_at": published_time,
                    "description": entry.get("summary", ""),
                }
            )

    return videos


def scrape_channel(channel_id: str, hours: int = 150) -> list[dict]:
    videos = get_latest_videos(channel_id, hours)
    for video in videos:
        transcript: Optional[str] = get_transcript(video["video_id"])
        video["transcript"] = transcript
    return videos


if __name__ == "__main__":
    channel_id = "UCcvjK35lDPZTlkIrrwxpepg"
    videos = get_latest_videos(channel_id=channel_id, hours=200)
    print(videos)

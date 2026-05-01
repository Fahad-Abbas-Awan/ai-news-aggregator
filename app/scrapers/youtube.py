from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import requests
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled


FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


class Transcript(BaseModel):
    text: str


class ChannelVideo(BaseModel):
    title: str
    url: str
    video_id: str
    published_at: datetime
    description: str
    transcript: Optional[str] = None


class YouTubeScraper:
    def __init__(self):
        self.transcript_api = YouTubeTranscriptApi()

    def get_rss_url(self, channel_id: str) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def fetch_feed(self, channel_id: str):
        response = requests.get(self.get_rss_url(channel_id), headers=FEED_HEADERS, timeout=20)
        response.raise_for_status()
        return feedparser.parse(response.content)

    def extract_video_id(self, video_url: str) -> str:
        if "youtube.com/watch?v=" in video_url:
            return video_url.split("v=")[1].split("&")[0]
        if "youtube.com/shorts/" in video_url:
            return video_url.split("shorts/")[1].split("?")[0]
        if "youtu.be/" in video_url:
            return video_url.split("youtu.be/")[1].split("?")[0]
        return video_url

    def get_latest_videos(self, channel_id: str, hours: int = 200) -> list[ChannelVideo]:
        try:
            feed = self.fetch_feed(channel_id)
        except Exception:
            return []

        if not feed.entries:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        videos = []

        for entry in feed.entries:
            if "/shorts/" in entry.link:
                continue

            published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published_time >= cutoff_time:
                video_id = self.extract_video_id(entry.link)
                videos.append(
                    ChannelVideo(
                        title=entry.title,
                        url=entry.link,
                        video_id=video_id,
                        published_at=published_time,
                        description=entry.get("summary", ""),
                    )
                )

        return videos

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            transcript = self.transcript_api.fetch(video_id)
            text = " ".join(snippet.text for snippet in transcript.snippets)
            return Transcript(text=text)
        except (TranscriptsDisabled, NoTranscriptFound):
            return None
        except Exception:
            return None

    def scrape_channel(self, channel_id: str, hours: int = 200) -> list[ChannelVideo]:
        videos = self.get_latest_videos(channel_id, hours)
        for video in videos:
            transcript_result = self.get_transcript(video.video_id)
            video.transcript = transcript_result.text if transcript_result else None
        return videos


_default_scraper = YouTubeScraper()


def get_rss_url(channel_id: str) -> str:
    return _default_scraper.get_rss_url(channel_id)


def extract_video_id(video_url: str) -> str:
    return _default_scraper.extract_video_id(video_url)


def get_latest_videos(channel_id: str, hours: int = 200) -> list[ChannelVideo]:
    return _default_scraper.get_latest_videos(channel_id, hours)


def get_transcript(video_id: str) -> Optional[Transcript]:
    return _default_scraper.get_transcript(video_id)


def scrape_channel(channel_id: str, hours: int = 200) -> list[ChannelVideo]:
    return _default_scraper.scrape_channel(channel_id, hours)

from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Optional

import feedparser
import requests
import yt_dlp
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

    def get_channel_videos_url(self, channel_id: str) -> str:
        return f"https://www.youtube.com/channel/{channel_id}/videos"

    def _extract_yt_initial_data(self, html: str) -> dict[str, Any] | None:
        match = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.DOTALL)
        if not match:
            match = re.search(r"ytInitialData\"\]\s*=\s*(\{.*?\});", html, re.DOTALL)
        if not match:
            return None

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _walk_for_video_renderers(self, obj: Any, acc: list[dict[str, Any]]) -> None:
        if isinstance(obj, dict):
            if "videoRenderer" in obj and isinstance(obj["videoRenderer"], dict):
                acc.append(obj["videoRenderer"])
            for value in obj.values():
                self._walk_for_video_renderers(value, acc)
        elif isinstance(obj, list):
            for item in obj:
                self._walk_for_video_renderers(item, acc)

    def _relative_time_to_datetime(self, published_text: str) -> datetime | None:
        text = published_text.strip().lower()
        now = datetime.now(timezone.utc)

        if "just now" in text:
            return now

        match = re.search(r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago", text)
        if not match:
            return None

        amount = int(match.group(1))
        unit = match.group(2)

        if unit == "minute":
            return now - timedelta(minutes=amount)
        if unit == "hour":
            return now - timedelta(hours=amount)
        if unit == "day":
            return now - timedelta(days=amount)
        if unit == "week":
            return now - timedelta(weeks=amount)
        if unit == "month":
            return now - timedelta(days=amount * 30)
        if unit == "year":
            return now - timedelta(days=amount * 365)

        return None

    def get_latest_videos_from_channel_page(self, channel_id: str, hours: int = 200) -> list[ChannelVideo]:
        try:
            response = requests.get(
                self.get_channel_videos_url(channel_id),
                headers=FEED_HEADERS,
                timeout=20,
            )
            response.raise_for_status()
        except Exception:
            return []

        initial_data = self._extract_yt_initial_data(response.text)
        if not initial_data:
            return []

        renderers: list[dict[str, Any]] = []
        self._walk_for_video_renderers(initial_data, renderers)

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        seen_ids: set[str] = set()
        videos: list[ChannelVideo] = []

        for renderer in renderers:
            video_id = renderer.get("videoId")
            if not video_id or video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            # Skip shorts
            if renderer.get("isShort"):
                continue

            title_data = renderer.get("title", {})
            title_runs = title_data.get("runs", [])
            title_text = title_data.get("simpleText", "")
            if not title_text and title_runs:
                title_text = title_runs[0].get("text", "")

            published_text = (
                renderer.get("publishedTimeText", {}).get("simpleText", "")
            )
            published_time = self._relative_time_to_datetime(published_text)
            if not published_time or published_time < cutoff_time:
                continue

            description_runs = renderer.get("descriptionSnippet", {}).get("runs", [])
            description = "".join(run.get("text", "") for run in description_runs)

            videos.append(
                ChannelVideo(
                    title=title_text,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    video_id=video_id,
                    published_at=published_time,
                    description=description,
                )
            )

        return videos

    def get_latest_videos_with_yt_dlp(self, channel_id: str, hours: int = 200) -> list[ChannelVideo]:
        channel_url = self.get_channel_videos_url(channel_id)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            with yt_dlp.YoutubeDL(
                {
                    "quiet": True,
                    "skip_download": True,
                    "extract_flat": True,
                    "playlistend": 15,
                }
            ) as ydl:
                listing = ydl.extract_info(channel_url, download=False)
        except Exception:
            return []

        entries = listing.get("entries", []) if listing else []
        videos: list[ChannelVideo] = []

        try:
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                for entry in entries:
                    video_url = entry.get("url")
                    if not video_url:
                        continue

                    # Skip shorts
                    if "/shorts/" in video_url:
                        continue

                    info = ydl.extract_info(video_url, download=False)
                    if not info:
                        continue

                    timestamp = info.get("timestamp")
                    if not timestamp:
                        continue

                    published_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    if published_time < cutoff_time:
                        continue

                    video_id = info.get("id") or self.extract_video_id(video_url)
                    videos.append(
                        ChannelVideo(
                            title=info.get("title", ""),
                            url=video_url,
                            video_id=video_id,
                            published_at=published_time,
                            description=info.get("description", ""),
                        )
                    )
        except Exception:
            return []

        return videos

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
            videos = self.get_latest_videos_from_channel_page(channel_id, hours)
            return videos if videos else self.get_latest_videos_with_yt_dlp(channel_id, hours)

        if not feed.entries:
            videos = self.get_latest_videos_from_channel_page(channel_id, hours)
            return videos if videos else self.get_latest_videos_with_yt_dlp(channel_id, hours)

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

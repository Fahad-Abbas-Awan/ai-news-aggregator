from typing import Sequence

from sqlalchemy.orm import Session

from app.database.connection import get_session
from app.database.models import AnthropicArticle, OpenAIArticle, YouTubeVideo
from app.scrapers.anthropic import AnthropicArticle as ScrapedAnthropicArticle
from app.scrapers.openai import OpenAIArticle as ScrapedOpenAIArticle
from app.scrapers.youtube import ChannelVideo


class NewsRepository:
    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def get_youtube_video(self, video_id: str) -> YouTubeVideo | None:
        return self.session.get(YouTubeVideo, video_id)

    def get_openai_article(self, guid: str) -> OpenAIArticle | None:
        return self.session.get(OpenAIArticle, guid)

    def get_anthropic_article(self, guid: str) -> AnthropicArticle | None:
        return self.session.get(AnthropicArticle, guid)

    def save_youtube_videos(self, channel_id: str, videos: Sequence[ChannelVideo]) -> int:
        inserted = 0
        for video in videos:
            if self.session.get(YouTubeVideo, video.video_id):
                continue

            self.session.add(
                YouTubeVideo(
                    video_id=video.video_id,
                    title=video.title,
                    url=video.url,
                    channel_id=channel_id,
                    published_at=video.published_at,
                    description=video.description,
                    transcript=video.transcript,
                )
            )
            inserted += 1

        self.session.commit()
        return inserted

    def update_youtube_transcript(self, video_id: str, transcript: str) -> bool:
        video = self.session.get(YouTubeVideo, video_id)
        if not video:
            return False

        video.transcript = transcript
        self.session.commit()
        return True

    def save_openai_articles(self, articles: Sequence[ScrapedOpenAIArticle]) -> int:
        inserted = 0
        for article in articles:
            if self.session.get(OpenAIArticle, article.guid):
                continue

            self.session.add(
                OpenAIArticle(
                    guid=article.guid,
                    title=article.title,
                    url=article.url,
                    description=article.description,
                    published_at=article.published_at,
                    category=article.category,
                )
            )
            inserted += 1

        self.session.commit()
        return inserted

    def save_anthropic_articles(self, articles: Sequence[ScrapedAnthropicArticle]) -> int:
        inserted = 0
        for article in articles:
            if self.session.get(AnthropicArticle, article.guid):
                continue

            self.session.add(
                AnthropicArticle(
                    guid=article.guid,
                    title=article.title,
                    url=article.url,
                    description=article.description,
                    published_at=article.published_at,
                    category=article.category,
                    markdown=article.markdown,
                )
            )
            inserted += 1

        self.session.commit()
        return inserted

    def update_anthropic_markdown(self, guid: str, markdown: str) -> bool:
        article = self.session.get(AnthropicArticle, guid)
        if not article:
            return False

        article.markdown = markdown
        self.session.commit()
        return True

    def delete_youtube_video(self, video_id: str) -> bool:
        video = self.session.get(YouTubeVideo, video_id)
        if not video:
            return False

        self.session.delete(video)
        self.session.commit()
        return True

    def delete_openai_article(self, guid: str) -> bool:
        article = self.session.get(OpenAIArticle, guid)
        if not article:
            return False

        self.session.delete(article)
        self.session.commit()
        return True

    def delete_anthropic_article(self, guid: str) -> bool:
        article = self.session.get(AnthropicArticle, guid)
        if not article:
            return False

        self.session.delete(article)
        self.session.commit()
        return True

    def close(self) -> None:
        self.session.close()

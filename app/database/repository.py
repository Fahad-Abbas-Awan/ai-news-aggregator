from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.database.connection import get_session
from app.database.models import AnthropicArticle, Digest, OpenAIArticle, YouTubeVideo
from app.scrapers.anthropic import AnthropicArticle as ScrapedAnthropicArticle
from app.scrapers.openai import OpenAIArticle as ScrapedOpenAIArticle
from app.scrapers.youtube import ChannelVideo


TRANSCRIPT_UNAVAILABLE_MARKER = "__UNAVAILABLE__"


class NewsRepository:
    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def get_youtube_video(self, video_id: str) -> YouTubeVideo | None:
        return self.session.get(YouTubeVideo, video_id)

    def get_openai_article(self, guid: str) -> OpenAIArticle | None:
        return self.session.get(OpenAIArticle, guid)

    def get_anthropic_article(self, guid: str) -> AnthropicArticle | None:
        return self.session.get(AnthropicArticle, guid)

    def get_youtube_videos_without_transcript(self, limit: int | None = None) -> list[YouTubeVideo]:
        query = self.session.query(YouTubeVideo).filter(YouTubeVideo.transcript.is_(None))
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def get_anthropic_articles_without_markdown(self, limit: int | None = None) -> list[AnthropicArticle]:
        query = self.session.query(AnthropicArticle).filter(AnthropicArticle.markdown.is_(None))
        if limit is not None:
            query = query.limit(limit)
        return query.all()

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

    def update_youtube_video_transcript(self, video_id: str, transcript: str) -> bool:
        return self.update_youtube_transcript(video_id, transcript)

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

    def update_anthropic_article_markdown(self, guid: str, markdown: str) -> bool:
        return self.update_anthropic_markdown(guid, markdown)

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

    def get_articles_without_digest(self, limit: int | None = None) -> list[dict[str, Any]]:
        digests = self.session.query(Digest).all()
        seen_ids = {f"{digest.article_type}:{digest.article_id}" for digest in digests}

        articles: list[dict[str, Any]] = []

        youtube_videos = self.session.query(YouTubeVideo).all()
        for video in youtube_videos:
            key = f"youtube:{video.video_id}"
            if key in seen_ids:
                continue

            content = video.transcript
            if not content or content == TRANSCRIPT_UNAVAILABLE_MARKER:
                content = video.description or ""

            articles.append(
                {
                    "type": "youtube",
                    "id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "content": content,
                    "published_at": video.published_at,
                }
            )

        openai_articles = self.session.query(OpenAIArticle).all()
        for article in openai_articles:
            key = f"openai:{article.guid}"
            if key in seen_ids:
                continue

            articles.append(
                {
                    "type": "openai",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.description or "",
                    "published_at": article.published_at,
                }
            )

        anthropic_articles = self.session.query(AnthropicArticle).all()
        for article in anthropic_articles:
            key = f"anthropic:{article.guid}"
            if key in seen_ids:
                continue

            articles.append(
                {
                    "type": "anthropic",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.markdown or article.description or "",
                    "published_at": article.published_at,
                }
            )

        articles.sort(key=lambda article: article["published_at"], reverse=True)

        if limit is not None:
            articles = articles[:limit]

        return articles

    def create_digest(
        self,
        article_type: str,
        article_id: str,
        url: str,
        title: str,
        summary: str,
        published_at: datetime | None = None,
    ) -> Digest | None:
        digest_id = f"{article_type}:{article_id}"
        if self.session.get(Digest, digest_id):
            return None

        created_at = published_at
        if created_at is None:
            created_at = datetime.now(timezone.utc)
        elif created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        digest = Digest(
            id=digest_id,
            article_type=article_type,
            article_id=article_id,
            url=url,
            title=title,
            summary=summary,
            created_at=created_at,
        )
        self.session.add(digest)
        self.session.commit()
        return digest

    def close(self) -> None:
        self.session.close()

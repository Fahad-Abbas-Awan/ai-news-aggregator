from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled


def get_transcript(video_id: str) -> Optional[str]:
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)
        return " ".join(snippet.text for snippet in transcript.snippets)
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception:
        return None


if __name__ == "__main__":
    print(get_transcript("jqd6_bbjhS8"))

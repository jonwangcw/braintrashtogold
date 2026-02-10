import tempfile

from yt_dlp import YoutubeDL

from app.processing.transcribe import transcribe_audio


def get_youtube_duration_seconds(url: str) -> int:
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return int(info.get("duration") or 0)


async def ingest_youtube(url: str) -> str:
    duration = get_youtube_duration_seconds(url)
    if duration > 3600:
        raise ValueError("YouTube video exceeds 1 hour limit")
    with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
        return await transcribe_audio(tmp.name)

import tempfile

from app.processing.transcribe import transcribe_audio


async def ingest_youtube(url: str) -> str:
    # Placeholder: implement yt-dlp download and duration checks.
    with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
        return await transcribe_audio(tmp.name)

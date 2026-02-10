from pathlib import Path
from tempfile import TemporaryDirectory

from yt_dlp import YoutubeDL

from app.processing.transcribe import transcribe_audio


MAX_DURATION_SECONDS = 3600


def get_youtube_duration_seconds(url: str) -> int:
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return int(info.get("duration") or 0)


def download_youtube_audio(url: str, output_dir: str) -> str:
    outtmpl = str(Path(output_dir) / "audio.%(ext)s")
    opts = {
        "quiet": True,
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded_path = Path(ydl.prepare_filename(info))

    if downloaded_path.exists():
        return str(downloaded_path)

    matching = sorted(Path(output_dir).glob("audio.*"))
    if not matching:
        raise ValueError("Unable to download YouTube audio")
    return str(matching[0])


async def ingest_youtube(url: str) -> str:
    duration = get_youtube_duration_seconds(url)
    if duration > MAX_DURATION_SECONDS:
        raise ValueError("YouTube video exceeds 1 hour limit")

    with TemporaryDirectory() as temp_dir:
        audio_path = download_youtube_audio(url, temp_dir)
        return await transcribe_audio(audio_path)

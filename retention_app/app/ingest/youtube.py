from pathlib import Path
from tempfile import TemporaryDirectory

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.processing.transcribe import transcribe_audio


MAX_DURATION_SECONDS = 3600


def _youtube_base_options() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # Force yt-dlp to use Node.js when JavaScript runtime execution is required.
        "js_runtimes": {"node": {"path": "node"}},
        "js_runtime": "node",
    }


def _youtube_audio_download_options(output_dir: str) -> dict:
    outtmpl = str(Path(output_dir) / "audio.%(ext)s")
    return {
        **_youtube_base_options(),
        # Ask yt-dlp for the best available audio-only stream and avoid
        # ambiguous fallback chains that can fail with unavailable format IDs.
        "format": "bestaudio",
        "outtmpl": outtmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "prefer_ffmpeg": True,
    }


def get_youtube_duration_seconds(url: str) -> int:
    opts = _youtube_base_options()
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return int(info.get("duration") or 0)


def download_youtube_audio(url: str, output_dir: str) -> str:
    opts = _youtube_audio_download_options(output_dir)
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        _ = ydl.prepare_filename(info)

    converted_path = Path(output_dir) / "audio.mp3"
    if converted_path.exists():
        return str(converted_path)

    matching = sorted(Path(output_dir).glob("audio.*"))
    if not matching:
        raise ValueError("Unable to download YouTube audio")
    return str(matching[0])


async def ingest_youtube(url: str) -> str:
    try:
        duration = get_youtube_duration_seconds(url)
        if duration > MAX_DURATION_SECONDS:
            raise ValueError("YouTube video exceeds 1 hour limit")

        with TemporaryDirectory() as temp_dir:
            audio_path = download_youtube_audio(url, temp_dir)
            return await transcribe_audio(audio_path)
    except DownloadError as exc:
        raise ValueError(
            "YouTube extraction failed. Install a JS runtime (Node.js or Deno) for yt-dlp and retry. "
            f"Underlying error: {exc}"
        ) from exc

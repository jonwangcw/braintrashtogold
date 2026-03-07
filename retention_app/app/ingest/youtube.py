import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.processing.transcribe import transcribe_audio
from app.processing.ocr import OCRSnippet, ocr_frames
from app.processing.transcript_reconcile import ReconciledTranscript


MAX_DURATION_SECONDS = 3600


@dataclass
class _YouTubeMeta:
    duration_seconds: int
    title: str | None
    uploader: str | None


@dataclass
class YouTubeIngestResult:
    raw_transcript: str
    corrected_transcript: str
    ocr_snippets: list[OCRSnippet]
    reconciliation: ReconciledTranscript
    artifact_dir: str | None = None
    reconciliation_notes: str | None = None
    title: str | None = None


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


def _get_youtube_metadata(url: str) -> _YouTubeMeta:
    opts = _youtube_base_options()
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return _YouTubeMeta(
        duration_seconds=int(info.get("duration") or 0),
        title=info.get("title") or None,
        uploader=info.get("uploader") or info.get("channel") or None,
    )


def get_youtube_duration_seconds(url: str) -> int:
    return _get_youtube_metadata(url).duration_seconds


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


def _probe_video_duration_seconds(video_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        video_path,
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout or "{}")
    return float(payload.get("format", {}).get("duration", 0.0) or 0.0)


def _extract_frames_every_n_seconds(video_path: str, output_dir: str, interval_seconds: int = 15) -> list[str]:
    frame_dir = Path(output_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_pattern = str(frame_dir / "frame_%06d.jpg")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        video_path,
        "-vf",
        f"fps=1/{max(1, interval_seconds)}",
        "-q:v",
        "2",
        frame_pattern,
    ]
    subprocess.run(cmd, check=True)
    return [str(path) for path in sorted(frame_dir.glob("frame_*.jpg"))]


def download_youtube_video(url: str, output_dir: str) -> str:
    outtmpl = str(Path(output_dir) / "video.%(ext)s")
    opts = {
        **_youtube_base_options(),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "prefer_ffmpeg": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        _ = ydl.prepare_filename(info)

    converted_path = Path(output_dir) / "video.mp4"
    if converted_path.exists():
        return str(converted_path)

    matching = sorted(Path(output_dir).glob("video.*"))
    if not matching:
        raise ValueError("Unable to download YouTube video for OCR")
    return str(matching[0])


async def _llm_reconcile(raw_transcript: str, ocr_snippets: list[OCRSnippet]) -> tuple[str, str]:
    import json as _json
    from app.llm.openrouter_client import OpenRouterClient
    from app.llm.prompts import reconciliation_prompt
    ocr_corpus = "\n".join(
        f"[{int(s.timestamp_seconds)}s] {s.text}" for s in ocr_snippets
    )
    client = OpenRouterClient()
    raw = await client.complete(reconciliation_prompt(raw_transcript, ocr_corpus))
    try:
        stripped = raw.strip()
        # Strip optional markdown code fence
        if stripped.startswith("```"):
            stripped = stripped.split("```")[1]
            if stripped.startswith("json"):
                stripped = stripped[4:]
        payload = _json.loads(stripped)
        corrected = str(payload.get("corrected_transcript") or raw_transcript)
        changes = payload.get("changes") or []
        notes = "\n".join(str(c) for c in changes) if changes else ""
    except Exception:
        corrected = raw
        notes = ""
    return corrected, notes


def extract_video_frames_for_ocr(
    url: str,
    artifacts_dir: str,
    interval_seconds: int = 15,
) -> list[str]:
    with TemporaryDirectory() as temp_dir:
        video_path = download_youtube_video(url, temp_dir)
        duration = _probe_video_duration_seconds(video_path)
        frame_paths = _extract_frames_every_n_seconds(video_path, artifacts_dir, interval_seconds=interval_seconds)
        if duration > 0 and duration <= 120 and len(frame_paths) < 4:
            # Slightly denser extraction for short videos to improve OCR coverage.
            frame_paths = _extract_frames_every_n_seconds(
                video_path,
                artifacts_dir,
                interval_seconds=max(5, interval_seconds // 2),
            )
        return frame_paths


async def ingest_youtube(url: str, artifacts_dir: str | None = None) -> YouTubeIngestResult:
    try:
        meta = _get_youtube_metadata(url)
        if meta.duration_seconds > MAX_DURATION_SECONDS:
            raise ValueError("YouTube video exceeds 1 hour limit")
        if meta.title and meta.uploader:
            formatted_title = f"{meta.title} - {meta.uploader}"
        else:
            formatted_title = meta.title

        with TemporaryDirectory() as temp_dir:
            audio_path = download_youtube_audio(url, temp_dir)
            raw_transcript = await transcribe_audio(audio_path)

        ocr_snippets: list[OCRSnippet] = []
        if artifacts_dir:
            frame_paths = extract_video_frames_for_ocr(url, artifacts_dir)
            ocr_snippets = ocr_frames(frame_paths)

        reconciliation_notes: str | None = None
        if ocr_snippets:
            corrected_transcript, reconciliation_notes = await _llm_reconcile(raw_transcript, ocr_snippets)
        else:
            corrected_transcript = raw_transcript
        reconciliation = ReconciledTranscript(corrected_transcript=corrected_transcript, corrections=[])
        return YouTubeIngestResult(
            raw_transcript=raw_transcript,
            corrected_transcript=corrected_transcript,
            ocr_snippets=ocr_snippets,
            reconciliation=reconciliation,
            artifact_dir=artifacts_dir,
            reconciliation_notes=reconciliation_notes,
            title=formatted_title,
        )
    except DownloadError as exc:
        raise ValueError(
            "YouTube extraction failed. Install a JS runtime (Node.js or Deno) for yt-dlp and retry. "
            f"Underlying error: {exc}"
        ) from exc

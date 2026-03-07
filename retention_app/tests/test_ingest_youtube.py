import asyncio

import pytest

yt_dlp = pytest.importorskip("yt_dlp")
DownloadError = yt_dlp.utils.DownloadError

from app.ingest import youtube as youtube_module


def _meta(duration_seconds, title=None, uploader=None):
    return youtube_module._YouTubeMeta(
        duration_seconds=duration_seconds, title=title, uploader=uploader
    )


def test_youtube_duration_cap(monkeypatch):
    monkeypatch.setattr(youtube_module, "_get_youtube_metadata", lambda _: _meta(4000))
    with pytest.raises(ValueError, match="exceeds 1 hour"):
        asyncio.run(youtube_module.ingest_youtube("https://example.com/video"))


def test_youtube_ingest_downloads_and_transcribes(monkeypatch):
    monkeypatch.setattr(youtube_module, "_get_youtube_metadata", lambda _: _meta(120, "Test Video", "Test Channel"))
    monkeypatch.setattr(youtube_module, "download_youtube_audio", lambda url, output_dir: "/tmp/audio.mp3")

    async def fake_transcribe(path: str) -> str:
        assert path == "/tmp/audio.mp3"
        return "transcript"

    monkeypatch.setattr(youtube_module, "transcribe_audio", fake_transcribe)

    result = asyncio.run(youtube_module.ingest_youtube("https://example.com/video"))
    assert result.raw_transcript == "transcript"
    assert result.corrected_transcript == "transcript"
    assert result.ocr_snippets == []


def test_youtube_ingest_wraps_download_error(monkeypatch):
    monkeypatch.setattr(youtube_module, "_get_youtube_metadata", lambda _: _meta(120))

    def raise_download_error(url, output_dir):
        raise DownloadError("No supported JavaScript runtime")

    monkeypatch.setattr(youtube_module, "download_youtube_audio", raise_download_error)

    with pytest.raises(ValueError, match="Install a JS runtime"):
        asyncio.run(youtube_module.ingest_youtube("https://example.com/video"))


def test_youtube_base_options_enable_node_runtime():
    opts = youtube_module._youtube_base_options()
    assert opts["js_runtime"] == "node"
    assert opts["js_runtimes"]["node"]["path"] == "node"


def test_youtube_audio_download_options_are_unambiguous_and_convert_to_mp3(tmp_path):
    opts = youtube_module._youtube_audio_download_options(str(tmp_path))

    assert opts["format"] == "bestaudio"
    assert opts["prefer_ffmpeg"] is True
    assert opts["outtmpl"].endswith("audio.%(ext)s")
    assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
    assert opts["postprocessors"][0]["preferredcodec"] == "mp3"

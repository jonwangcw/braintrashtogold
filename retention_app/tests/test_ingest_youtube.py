import asyncio

import pytest

pytest.importorskip("yt_dlp")

from app.ingest import youtube as youtube_module


def test_youtube_duration_cap(monkeypatch):
    monkeypatch.setattr(youtube_module, "get_youtube_duration_seconds", lambda _: 4000)
    with pytest.raises(ValueError, match="exceeds 1 hour"):
        asyncio.run(youtube_module.ingest_youtube("https://example.com/video"))


def test_youtube_ingest_downloads_and_transcribes(monkeypatch):
    monkeypatch.setattr(youtube_module, "get_youtube_duration_seconds", lambda _: 120)
    monkeypatch.setattr(youtube_module, "download_youtube_audio", lambda url, output_dir: "/tmp/audio.mp3")

    async def fake_transcribe(path: str) -> str:
        assert path == "/tmp/audio.mp3"
        return "transcript"

    monkeypatch.setattr(youtube_module, "transcribe_audio", fake_transcribe)

    result = asyncio.run(youtube_module.ingest_youtube("https://example.com/video"))
    assert result == "transcript"

import asyncio

import pytest

pytest.importorskip("yt_dlp")

from app.ingest import youtube as youtube_module


def test_youtube_duration_cap(monkeypatch):
    monkeypatch.setattr(youtube_module, "get_youtube_duration_seconds", lambda _: 4000)
    with pytest.raises(ValueError, match="exceeds 1 hour"):
        asyncio.run(youtube_module.ingest_youtube("https://example.com/video"))

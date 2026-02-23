import asyncio

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("yt_dlp")
pytest.importorskip("trafilatura")

from app.ingest import router


def test_ingest_router_cleans_webpage_text(monkeypatch):
    monkeypatch.setattr(router, "validate_url", lambda url: None)
    monkeypatch.setattr(router, "extract_webpage_text", lambda url: "Hello    world")

    cleaned = asyncio.run(router.ingest_source("webpage", "https://example.com"))

    assert cleaned.cleaned_text == "Hello world"


def test_ingest_router_rejects_youtube_url_for_webpage_source(monkeypatch):
    monkeypatch.setattr(router, "validate_url", lambda url: None)
    with pytest.raises(ValueError, match="must use source type youtube"):
        asyncio.run(router.ingest_source("webpage", "https://www.youtube.com/watch?v=abc"))

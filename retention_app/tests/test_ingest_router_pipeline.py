import asyncio

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("yt_dlp")
pytest.importorskip("trafilatura")

from app.ingest import router


def test_ingest_router_cleans_webpage_text(monkeypatch):
    monkeypatch.setattr(router, "validate_url", lambda url: None)
    monkeypatch.setattr(router, "extract_webpage_text", lambda url: ("Hello    world", None))

    cleaned = asyncio.run(router.ingest_source(None, "https://example.com"))

    assert cleaned.cleaned_text == "Hello world"


def test_ingest_router_detects_youtube_source(monkeypatch):
    monkeypatch.setattr(router, "validate_url", lambda url: None)
    monkeypatch.setattr(router, "detect_source_type", lambda url: "youtube")

    async def fake_ingest_youtube(url: str, artifacts_dir: str | None = None):
        class _Correction:
            original = "foo"
            corrected = "bar"
            confidence = 0.9

        class _Snippet:
            timestamp_seconds = 0
            confidence = 0.88
            text = "hello"

        class _Reconciliation:
            corrections = [_Correction()]

        class _Result:
            corrected_transcript = "Transcript"
            raw_transcript = "Raw"
            reconciliation = _Reconciliation()
            ocr_snippets = [_Snippet()]
            title = None

        return _Result()

    monkeypatch.setattr(router, "ingest_youtube", fake_ingest_youtube)

    payload = asyncio.run(router.ingest_source(None, "https://www.youtube.com/watch?v=abc"))

    assert payload.source_type == "youtube"
    assert payload.cleaned_text == "Transcript"


def test_ingest_router_explicit_pdf_source_type_uses_local_path(monkeypatch):
    monkeypatch.setattr(router, "extract_text_from_pdf", lambda path: "PDF   text")
    monkeypatch.setattr(router, "extract_pdf_title", lambda path: None)

    payload = asyncio.run(router.ingest_source("pdf", "/tmp/file.pdf"))

    assert payload.source_type == "pdf"
    assert payload.cleaned_text == "PDF text"

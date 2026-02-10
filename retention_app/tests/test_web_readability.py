from types import SimpleNamespace

import pytest

pytest.importorskip("httpx")
pytest.importorskip("trafilatura")

from app.ingest import web as web_module


def test_web_readability_extracts_text(monkeypatch):
    def fake_get(url, timeout=30):
        return SimpleNamespace(text="<html><body>Hello world</body></html>", raise_for_status=lambda: None)

    monkeypatch.setattr(web_module.httpx, "get", fake_get)
    monkeypatch.setattr(web_module.trafilatura, "extract", lambda _: "Hello world")
    assert web_module.extract_webpage_text("https://example.com") == "Hello world"

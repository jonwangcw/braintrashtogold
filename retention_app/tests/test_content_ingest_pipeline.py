import asyncio

import pytest

pytest.importorskip("sqlalchemy")

from app.db.engine import Base, engine, SessionLocal
from app.db import models
from app.ingest.router import IngestedContentPayload
from app.services import content_service


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_ingest_pipeline_accesses_source_produces_clean_text_and_calls_llm(monkeypatch):
    calls = {"source_url": None, "llm_text": None}

    async def fake_ingest_source(source_type: str, url: str, artifacts_dir: str | None = None) -> IngestedContentPayload:
        calls["source_url"] = url
        return IngestedContentPayload(
            cleaned_text="Raw   text\n\nfrom source",
            raw_transcript="raw",
            corrected_transcript="corrected",
            ocr_text_corpus="ocr",
            correction_annotations="termx -> TermX (confidence=0.91)",
        )

    async def fake_create_question_set(session, content_id, cleaned_text, kind, correction_hints=None):
        calls["llm_text"] = cleaned_text
        return None

    monkeypatch.setattr(content_service, "ingest_source", fake_ingest_source)
    monkeypatch.setattr(content_service, "create_question_set", fake_create_question_set)

    with SessionLocal() as session:
        content = asyncio.run(
            content_service.ingest_content(
                session=session,
                title="Example",
                source_type="webpage",
                url="https://example.com/article",
            )
        )
        stored = session.get(models.ContentText, content.id)

    assert calls["source_url"] == "https://example.com/article"
    assert stored is not None
    assert stored.cleaned_text == "Raw   text\n\nfrom source"
    assert stored.raw_transcript == "raw"
    assert stored.corrected_transcript == "corrected"
    assert calls["llm_text"] == "Raw   text\n\nfrom source"


def test_ingest_pipeline_marks_error_when_source_access_fails(monkeypatch):
    async def failing_ingest_source(source_type: str, url: str, artifacts_dir: str | None = None) -> IngestedContentPayload:
        raise RuntimeError("source unreachable")

    monkeypatch.setattr(content_service, "ingest_source", failing_ingest_source)

    with SessionLocal() as session:
        content = asyncio.run(
            content_service.ingest_content(
                session=session,
                title="Broken",
                source_type="webpage",
                url="https://example.com/broken",
            )
        )
        session.refresh(content)

    assert content.status == models.ContentStatus.error
    assert "source unreachable" in (content.error_message or "")

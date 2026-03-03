from datetime import datetime
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("starlette")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient

from app.db import models
from app.db.engine import Base, SessionLocal, engine
from app.main import app
from app import main as main_module


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_homepage_smoke():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200


def test_scheduled_quiz_displays_generated_questions():
    with SessionLocal() as session:
        content = models.Content(
            title="Example",
            content_type=models.ContentType.webpage,
            source_url="https://example.com",
            status=models.ContentStatus.ready,
        )
        session.add(content)
        session.flush()

        question_set = models.QuestionSet(
            content_id=content.id,
            kind=models.QuestionSetKind.scheduled,
            generator_model="openrouter",
            generation_prompt_version="v1",
        )
        session.add(question_set)
        session.flush()

        session.add(
            models.Question(
                question_set_id=question_set.id,
                question_index=0,
                question_type=models.QuestionType.recall,
                prompt="What is retention?",
                expected_answer="Remembering key points",
                key_points_json='["memory"]',
                sources_json='[{"quote":"retention","start_char":0,"end_char":9}]',
            )
        )
        session.commit()

    client = TestClient(app)
    response = client.get(f"/quiz/{content.id}/scheduled")

    assert response.status_code == 200
    assert "What is retention?" in response.text
    assert "Reveal answer" in response.text
    assert "Expected answer:" in response.text
    assert "name=\"comfort_rating\"" in response.text


def test_practice_quiz_hides_comfort_control():
    with SessionLocal() as session:
        content = models.Content(
            title="Example",
            content_type=models.ContentType.webpage,
            source_url="https://example.com",
            status=models.ContentStatus.ready,
        )
        session.add(content)
        session.commit()

    client = TestClient(app)
    response = client.get(f"/quiz/{content.id}/practice")

    assert response.status_code == 200
    assert "name=\"comfort_rating\"" not in response.text


def test_homepage_ingest_form_uses_auto_detection():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert 'name="source_type"' not in response.text
    assert 'name="url"' in response.text
    assert 'name="pdf_file"' in response.text


def test_ingest_local_pdf_upload(monkeypatch):
    captured = {}

    async def fake_ingest_content(session, title, source, source_url=None, source_type=None):
        captured["title"] = title
        captured["source"] = source
        captured["source_url"] = source_url
        captured["source_type"] = source_type

        class _Result:
            id = 1
            status = models.ContentStatus.ready
            error_message = None

        return _Result()

    monkeypatch.setattr(main_module, "ingest_content", fake_ingest_content)

    client = TestClient(app)
    response = client.post(
        "/ingest",
        data={"title": "Local PDF"},
        files={"pdf_file": ("notes.pdf", b"%PDF-1.4 fake", "application/pdf")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert captured["title"] == "Local PDF"
    assert captured["source_url"] == "local://notes.pdf"
    assert captured["source_type"] == "pdf"
    assert captured["source"].endswith(".pdf")


def test_due_concept_reviews_page_lists_due_items():
    with SessionLocal() as session:
        content = models.Content(
            title="Due Concept",
            content_type=models.ContentType.webpage,
            source_url="https://example.com/due",
            status=models.ContentStatus.ready,
        )
        session.add(content)
        session.flush()

        session.add(
            models.ScheduleState(
                content_id=content.id,
                step_index=0,
                next_due_at=datetime.utcnow(),
                is_terminated=False,
            )
        )

        question_set = models.QuestionSet(
            content_id=content.id,
            kind=models.QuestionSetKind.scheduled,
            generator_model="openrouter",
            generation_prompt_version="v1",
        )
        session.add(question_set)
        session.flush()

        session.add(
            models.Question(
                question_set_id=question_set.id,
                question_index=0,
                question_type=models.QuestionType.recall,
                prompt="Define retrieval practice",
                expected_answer="Active recall",
                key_points_json='["Retrieval practice"]',
                sources_json='[{"quote":"Retrieval practice improves memory","start_char":0,"end_char":34}]',
            )
        )
        session.commit()

    client = TestClient(app)
    response = client.get("/concept-review/due")

    assert response.status_code == 200
    assert "Due concept reviews" in response.text
    assert f"/concept-review/{content.id}/" in response.text


def test_concept_probe_contains_required_fields_and_accepts_submit():
    with SessionLocal() as session:
        content = models.Content(
            title="Probe Content",
            content_type=models.ContentType.webpage,
            source_url="https://example.com/probe",
            status=models.ContentStatus.ready,
        )
        session.add(content)
        session.flush()

        session.add(
            models.ScheduleState(
                content_id=content.id,
                step_index=1,
                next_due_at=datetime.utcnow(),
                is_terminated=False,
            )
        )

        question_set = models.QuestionSet(
            content_id=content.id,
            kind=models.QuestionSetKind.scheduled,
            generator_model="openrouter",
            generation_prompt_version="v1",
        )
        session.add(question_set)
        session.flush()

        question = models.Question(
            question_set_id=question_set.id,
            question_index=0,
            question_type=models.QuestionType.explain,
            prompt="Explain spaced repetition",
            expected_answer="Spacing reviews over time",
            key_points_json='["Spaced repetition"]',
            sources_json='[{"quote":"Spacing supports long-term retention","start_char":10,"end_char":45}]',
        )
        session.add(question)
        session.commit()

    client = TestClient(app)
    page = client.get(f"/concept-review/{content.id}/{question.id}")
    assert page.status_code == 200
    assert 'name="content_id"' in page.text
    assert 'name="concept_id"' in page.text
    assert 'name="probe_id"' in page.text
    assert 'name="comfort_level"' in page.text

    submit = client.post(
        "/concept-review/submit",
        data={
            "content_id": content.id,
            "concept_id": question.id,
            "probe_id": question.id,
            "comfort_level": 3,
        },
        follow_redirects=False,
    )
    assert submit.status_code == 303
    assert "submitted=1" in submit.headers["location"]


def test_navigation_links_concept_review_workflow():
    with SessionLocal() as session:
        content = models.Content(
            title="Navigation Concept",
            content_type=models.ContentType.webpage,
            source_url="https://example.com/nav",
            status=models.ContentStatus.ready,
        )
        session.add(content)
        session.flush()

        session.add(models.ScheduleState(content_id=content.id, step_index=0, is_terminated=False))
        question_set = models.QuestionSet(
            content_id=content.id,
            kind=models.QuestionSetKind.scheduled,
            generator_model="openrouter",
            generation_prompt_version="v1",
        )
        session.add(question_set)
        session.flush()
        session.add(
            models.Question(
                question_set_id=question_set.id,
                question_index=0,
                question_type=models.QuestionType.recall,
                prompt="What is a cue?",
                expected_answer="Memory trigger",
                key_points_json='["Cue"]',
                sources_json='[{"quote":"Cue supports recall","start_char":1,"end_char":20}]',
            )
        )
        session.commit()

    client = TestClient(app)
    home = client.get("/")
    assert '/concept-review/due' in home.text

    detail = client.get(f"/content/{content.id}")
    assert '/concept-review/due' in detail.text
    assert f'/concept-review/{content.id}/' in detail.text

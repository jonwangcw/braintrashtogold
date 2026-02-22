import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("starlette")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient

from app.db import models
from app.db.engine import Base, SessionLocal, engine
from app.main import app


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

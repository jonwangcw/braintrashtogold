from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import models
from app.db.engine import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _seed_due_concept() -> tuple[int, int]:
    with SessionLocal() as session:
        content = models.Content(
            title="Retention 101",
            content_type=models.ContentType.webpage,
            source_url="https://example.com",
            status=models.ContentStatus.ready,
        )
        session.add(content)
        session.flush()

        concept = models.Concept(content_id=content.id, title="Spacing", summary="Study over time")
        session.add(concept)
        session.flush()

        schedule = models.ConceptSchedule(
            concept_id=concept.id,
            step_index=0,
            next_due_at=datetime.utcnow() - timedelta(minutes=5),
            is_terminated=False,
        )
        session.add(schedule)
        session.commit()
        return content.id, concept.id


def test_due_reviews_generates_probe_and_returns_concept():
    _, concept_id = _seed_due_concept()
    client = TestClient(app)

    response = client.get("/reviews/due?limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["concept_id"] == concept_id
    assert payload[0]["probe"]["probe_id"] > 0


def test_submit_review_persists_event_and_updates_schedule():
    _, concept_id = _seed_due_concept()
    client = TestClient(app)

    due_response = client.get("/reviews/due")
    probe_id = due_response.json()[0]["probe"]["probe_id"]

    submit_response = client.post(
        "/reviews/submit",
        json={
            "concept_id": concept_id,
            "probe_id": probe_id,
            "self_comfort": 4,
            "correctness": 1.0,
            "response_text": "Distributed practice boosts memory.",
        },
    )
    assert submit_response.status_code == 200
    result = submit_response.json()
    assert result["concept_id"] == concept_id
    assert result["step_index"] == 1

    with SessionLocal() as session:
        events = session.query(models.ReviewEvent).filter_by(concept_id=concept_id).all()
        assert len(events) == 1
        assert events[0].probe_id == probe_id

        schedule = session.get(models.ConceptSchedule, concept_id)
        assert schedule is not None
        assert schedule.last_score is not None
        assert schedule.step_index == 1


def test_concepts_endpoints():
    _, concept_id = _seed_due_concept()
    client = TestClient(app)

    list_response = client.get("/concepts")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == concept_id

    detail_response = client.get(f"/concepts/{concept_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == concept_id
    assert detail["probe"]["id"] > 0

import json

import pytest

pytest.importorskip("sqlalchemy")

from app.db.engine import Base, SessionLocal, engine
from app.db import models
from app.services import content_service
from app.services.content_service import ConceptCandidate, ConceptEvidenceCandidate


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_validate_evidence_spans_rejects_invalid_quotes_and_offsets():
    cleaned_text = "Alpha concept appears here.\n\nSecond paragraph."
    segments = content_service.stable_segment_text(cleaned_text, target_chunk_size=10)
    concepts = [
        ConceptCandidate(
            name="Alpha",
            summary="First concept",
            evidence=[
                ConceptEvidenceCandidate(quote="Alpha concept", start_char=0, end_char=13),
                ConceptEvidenceCandidate(quote="wrong text", start_char=0, end_char=10),
                ConceptEvidenceCandidate(quote="out", start_char=0, end_char=999),
            ],
        )
    ]

    validated = content_service.validate_evidence_spans(cleaned_text, segments, concepts)

    assert len(validated) == 1
    assert len(validated[0].evidence) == 1
    assert validated[0].evidence[0].quote == "Alpha concept"


def test_merge_threshold_behavior_merges_only_when_above_threshold():
    with SessionLocal() as session:
        content = models.Content(
            title="Doc",
            content_type=models.ContentType.webpage,
            source_url="https://example.com",
            status=models.ContentStatus.ready,
        )
        session.add(content)
        session.flush()

        segment = models.ContentSegment(
            content_id=content.id,
            chunk_index=0,
            start_char=0,
            end_char=25,
            text="Spaced repetition is useful",
        )
        session.add(segment)

        existing = models.Concept(
            canonical_name="Spaced repetition",
            aliases_json=json.dumps(["spacing effect"]),
            summary="learning technique",
        )
        session.add(existing)
        session.flush()
        session.add(
            models.ConceptSchedule(
                concept_id=existing.id,
                interval_days=3,
                due_at=content_service.datetime.utcnow(),
                reinforcement_count=0,
            )
        )
        session.commit()

        merge_candidate = ConceptCandidate(
            name="Spaced repitition",
            summary="updated summary",
            aliases=["distributed practice"],
            evidence=[
                ConceptEvidenceCandidate(
                    quote="Spaced repetition is useful",
                    start_char=0,
                    end_char=25,
                )
            ],
        )
        create_candidate = ConceptCandidate(
            name="Interleaving",
            summary="different concept",
            evidence=[
                ConceptEvidenceCandidate(
                    quote="Spaced repetition is useful",
                    start_char=0,
                    end_char=25,
                )
            ],
        )

        content_service._merge_or_create_concept(
            session=session,
            content_id=content.id,
            segments=[segment],
            candidate=merge_candidate,
            merge_threshold=0.8,
        )
        content_service._merge_or_create_concept(
            session=session,
            content_id=content.id,
            segments=[segment],
            candidate=create_candidate,
            merge_threshold=0.8,
        )
        session.commit()

        concepts = session.query(models.Concept).all()
        audits = session.query(models.ConceptMergeAudit).all()
        schedule = session.get(models.ConceptSchedule, existing.id)

    assert len(concepts) == 2
    assert len(audits) == 1
    assert schedule is not None
    assert schedule.interval_days == 4
    assert schedule.reinforcement_count == 1

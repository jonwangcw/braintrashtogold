from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.scheduling import strategy_v1


def _validate_self_comfort(self_comfort: int) -> None:
    if self_comfort < 1 or self_comfort > 5:
        raise ValueError("self_comfort must be between 1 and 5")


def _derive_score(self_comfort: int, correctness: float | None) -> float:
    comfort_score = float(self_comfort * 2)
    if correctness is None:
        return comfort_score

    bounded = min(max(correctness, 0.0), 1.0)
    return (comfort_score + (bounded * 10.0)) / 2.0


def fetch_due_concepts(session: Session, limit: int = 20) -> list[models.Concept]:
    now = datetime.utcnow()
    stmt = (
        select(models.Concept)
        .join(models.ConceptSchedule, models.ConceptSchedule.concept_id == models.Concept.id)
        .where(
            models.ConceptSchedule.is_terminated.is_(False),
            models.ConceptSchedule.next_due_at.is_not(None),
            models.ConceptSchedule.next_due_at <= now,
        )
        .order_by(models.ConceptSchedule.next_due_at.asc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def generate_or_reuse_probe(session: Session, concept_id: int) -> models.ConceptProbe:
    existing = session.execute(
        select(models.ConceptProbe)
        .where(
            models.ConceptProbe.concept_id == concept_id,
            models.ConceptProbe.status == models.ProbeStatus.active,
        )
        .order_by(models.ConceptProbe.created_at.desc())
    ).scalars().first()
    if existing is not None:
        return existing

    concept = session.get(models.Concept, concept_id)
    if concept is None:
        raise ValueError("concept not found")

    probe = models.ConceptProbe(
        concept_id=concept_id,
        prompt=f"In your own words, explain: {concept.title}",
        expected_answer=concept.summary,
        status=models.ProbeStatus.active,
    )
    session.add(probe)
    session.commit()
    session.refresh(probe)
    return probe


def submit_concept_review(
    session: Session,
    *,
    concept_id: int,
    probe_id: int,
    self_comfort: int,
    correctness: float | None = None,
    response_text: str | None = None,
) -> tuple[models.ReviewEvent, models.ConceptSchedule]:
    _validate_self_comfort(self_comfort)

    concept = session.get(models.Concept, concept_id)
    if concept is None:
        raise ValueError("concept not found")

    probe = session.get(models.ConceptProbe, probe_id)
    if probe is None or probe.concept_id != concept_id:
        raise ValueError("probe not found for concept")

    schedule = session.get(models.ConceptSchedule, concept_id)
    if schedule is None:
        schedule = models.ConceptSchedule(
            concept_id=concept_id,
            step_index=0,
            next_due_at=datetime.utcnow(),
            is_terminated=False,
        )
        session.add(schedule)
        session.flush()

    score = _derive_score(self_comfort, correctness)
    reviewed_at = datetime.utcnow()

    review_count = session.query(models.ReviewEvent).filter(models.ReviewEvent.concept_id == concept_id).count()
    decision = strategy_v1.next_concept_state(
        step_index=schedule.step_index,
        last_completed_at=reviewed_at,
        last_score=score,
        review_count=review_count,
    )

    event = models.ReviewEvent(
        concept_id=concept_id,
        probe_id=probe_id,
        self_comfort=self_comfort,
        correctness=correctness,
        response_text=response_text,
        score=score,
    )

    schedule.step_index = decision.next_step_index
    schedule.next_due_at = decision.next_due_at
    schedule.last_reviewed_at = reviewed_at
    schedule.last_score = score
    schedule.is_terminated = decision.terminate

    session.add(event)
    session.add(schedule)
    session.commit()
    session.refresh(event)
    session.refresh(schedule)
    return event, schedule

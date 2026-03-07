from datetime import datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from app.db import crud, models
from app.ingest.router import ingest_source
from app.llm.debug_logger import DebugLogger
from app.processing.chunking import TextChunk, stable_segment_text
from app.services.quiz_service import create_question_set


@dataclass
class ConceptEvidenceCandidate:
    quote: str
    start_char: int
    end_char: int
    confidence: float = 1.0


@dataclass
class ConceptCandidate:
    name: str
    summary: str
    aliases: list[str] = field(default_factory=list)
    evidence: list[ConceptEvidenceCandidate] = field(default_factory=list)


async def run_concept_extraction_pipeline(
    cleaned_text: str,
    segments: list[TextChunk],
) -> list[ConceptCandidate]:
    """Concept extraction entry point.

    This function is intentionally isolated so tests can patch LLM behavior.
    """
    _ = (cleaned_text, segments)
    return []


def _normalized(value: str) -> str:
    return " ".join(value.lower().split())


def _concept_similarity_score(candidate: ConceptCandidate, concept: models.Concept) -> float:
    aliases = {concept.canonical_name}
    try:
        aliases.update(json.loads(concept.aliases_json or "[]"))
    except json.JSONDecodeError:
        pass
    names_to_match = [candidate.name, *candidate.aliases]
    best = 0.0
    for name in names_to_match:
        norm_name = _normalized(name)
        for alias in aliases:
            best = max(best, SequenceMatcher(None, norm_name, _normalized(alias)).ratio())
    return best


def _find_segment_for_evidence(
    evidence: ConceptEvidenceCandidate,
    segments: list[TextChunk],
) -> TextChunk | None:
    for segment in segments:
        if evidence.start_char >= segment.start_char and evidence.end_char <= segment.end_char:
            return segment
    return None


def validate_evidence_spans(
    cleaned_text: str,
    segments: list[TextChunk],
    concepts: list[ConceptCandidate],
) -> list[ConceptCandidate]:
    valid_concepts: list[ConceptCandidate] = []
    for concept in concepts:
        valid_evidence: list[ConceptEvidenceCandidate] = []
        for evidence in concept.evidence:
            if evidence.start_char < 0 or evidence.end_char > len(cleaned_text):
                continue
            if evidence.start_char >= evidence.end_char:
                continue
            quote = cleaned_text[evidence.start_char : evidence.end_char]
            if _normalized(quote) != _normalized(evidence.quote):
                continue
            if _find_segment_for_evidence(evidence, segments) is None:
                continue
            valid_evidence.append(evidence)
        if valid_evidence:
            concept.evidence = valid_evidence
            valid_concepts.append(concept)
    return valid_concepts


def _merge_or_create_concept(
    session: Session,
    content_id: int,
    segments: list[models.ContentSegment],
    candidate: ConceptCandidate,
    merge_threshold: float = 0.85,
) -> None:
    concepts = session.query(models.Concept).all()
    best_match: models.Concept | None = None
    best_score = 0.0
    for concept in concepts:
        score = _concept_similarity_score(candidate, concept)
        if score > best_score:
            best_score = score
            best_match = concept

    if best_match is not None and best_score >= merge_threshold:
        existing_aliases = set(json.loads(best_match.aliases_json or "[]"))
        existing_aliases.update(candidate.aliases)
        existing_aliases.add(candidate.name)
        best_match.aliases_json = json.dumps(sorted(existing_aliases))
        if len(candidate.summary) > len(best_match.summary):
            best_match.summary = candidate.summary
        session.add(
            models.ConceptMergeAudit(
                source_concept_name=candidate.name,
                target_concept_id=best_match.id,
                similarity_score=best_score,
                rationale_json=json.dumps(
                    {
                        "threshold": merge_threshold,
                        "aliases_added": sorted(existing_aliases),
                    }
                ),
            )
        )
        concept = best_match
        schedule = session.get(models.ConceptSchedule, concept.id)
        if schedule:
            schedule.interval_days = min(schedule.interval_days + 1, 30)
            schedule.reinforcement_count += 1
            schedule.due_at = datetime.utcnow() + timedelta(days=schedule.interval_days)
            session.add(schedule)
    else:
        concept = models.Concept(
            canonical_name=candidate.name,
            aliases_json=json.dumps(sorted(set(candidate.aliases))),
            summary=candidate.summary,
        )
        session.add(concept)
        session.flush()
        session.add(
            models.ConceptSchedule(
                concept_id=concept.id,
                interval_days=1,
                due_at=datetime.utcnow() + timedelta(days=1),
                reinforcement_count=0,
            )
        )

    for evidence in candidate.evidence:
        segment = next(
            seg
            for seg in segments
            if evidence.start_char >= seg.start_char and evidence.end_char <= seg.end_char
        )
        session.add(
            models.ConceptEvidence(
                concept_id=concept.id,
                content_id=content_id,
                content_segment_id=segment.id,
                quote=evidence.quote,
                start_char=evidence.start_char,
                end_char=evidence.end_char,
                confidence=evidence.confidence,
            )
        )


async def process_concepts_for_content(session: Session, content_id: int, cleaned_text: str) -> None:
    chunk_candidates = stable_segment_text(cleaned_text)
    segment_records: list[models.ContentSegment] = []
    for index, chunk in enumerate(chunk_candidates):
        segment = models.ContentSegment(
            content_id=content_id,
            chunk_index=index,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            text=chunk.text,
        )
        session.add(segment)
        segment_records.append(segment)
    session.flush()

    extracted = await run_concept_extraction_pipeline(cleaned_text=cleaned_text, segments=chunk_candidates)
    validated = validate_evidence_spans(cleaned_text=cleaned_text, segments=chunk_candidates, concepts=extracted)

    for candidate in validated:
        _merge_or_create_concept(session, content_id, segment_records, candidate)

    session.commit()


async def ingest_content(
    session: Session,
    title: str,
    source: str,
    source_url: str | None = None,
    source_type: str | None = None,
    user_id: int | None = None,
) -> models.Content:
    if source_url is None:
        source_url = source
    logger.debug("ingest_content: title=%r source_url=%s", title, source_url)
    content = crud.create_content(session, title or source_url, models.ContentType.webpage, source_url, user_id=user_id)
    content_id = content.id
    logger.debug("ingest_content: created content_id=%s status=%s", content_id, content.status)
    try:
        logger.debug("ingest_content: calling ingest_source")
        artifacts_dir = Path("artifacts") / f"content_{content_id}"
        debug_logger = DebugLogger(content_id, artifacts_dir)
        payload = await ingest_source(source_type, source, artifacts_dir=str(artifacts_dir))
        content.content_type = models.ContentType(payload.source_type)
        if payload.title and not title:
            content.title = payload.title
            logger.debug("ingest_content: auto_title=%r", payload.title)
        cleaned_text = payload.cleaned_text
        logger.debug("ingest_content: ingest_source complete text_len=%d", len(cleaned_text))
        text_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

        debug_logger.section("RAW TRANSCRIPT", payload.raw_transcript or "(none)")
        debug_logger.section("RECONCILED TRANSCRIPT", payload.corrected_transcript or "(none)")
        debug_logger.section("RECONCILIATION CHANGES (LLM commentary)", payload.correction_annotations or "(none)")
        debug_logger.section("OCR TEXT CORPUS", payload.ocr_text_corpus or "(none)")

        top_corrections = []
        if payload.correction_annotations:
            top_corrections = payload.correction_annotations.splitlines()[:5]
        if top_corrections:
            logger.info(
                "ingest_content: transcript corrections content_id=%s corrections=%s",
                content_id,
                json.dumps(top_corrections),
            )

        content_text = models.ContentText(
            content_id=content_id,
            cleaned_text=cleaned_text,
            raw_transcript=payload.raw_transcript,
            corrected_transcript=payload.corrected_transcript,
            ocr_text_corpus=payload.ocr_text_corpus,
            correction_annotations=payload.correction_annotations,
            text_hash=text_hash,
        )
        session.add(content_text)
        session.commit()

        await process_concepts_for_content(session=session, content_id=content_id, cleaned_text=cleaned_text)

        logger.debug("ingest_content: calling create_question_set")
        await create_question_set(
            session=session,
            content_id=content_id,
            cleaned_text=cleaned_text,
            correction_hints=payload.correction_annotations,
            kind=models.QuestionSetKind.scheduled,
            debug_logger=debug_logger,
        )

        logger.debug("ingest_content: create_question_set complete")
        crud.set_content_ready(session, content)
        crud.init_schedule_state(session, content_id, datetime.utcnow() + timedelta(days=1))
        logger.debug("ingest_content: ready content_id=%s", content_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("ingest_content: failed content_id=%s", content_id, exc_info=True)
        session.rollback()
        crud.set_content_error(session, content, str(exc))
        logger.debug("ingest_content: error persisted content_id=%s", content_id)
    return content

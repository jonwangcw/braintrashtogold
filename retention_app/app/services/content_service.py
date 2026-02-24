from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import traceback

from sqlalchemy.orm import Session

from app.db import crud, models
from app.ingest.router import ingest_source
from app.services.quiz_service import create_question_set


async def ingest_content(
    session: Session,
    title: str,
    source_type: str,
    url: str,
) -> models.Content:
    print(f"[DEBUG] ingest_content:start title={title} source_type={source_type} url={url}")
    content = crud.create_content(session, title, models.ContentType(source_type), url)
    content_id = content.id
    print(f"[DEBUG] ingest_content:created content_id={content_id} status={content.status}")
    try:
        print("[DEBUG] ingest_content:calling ingest_source")
        artifacts_dir = Path("artifacts") / f"content_{content_id}"
        payload = await ingest_source(source_type, url, artifacts_dir=str(artifacts_dir))
        cleaned_text = payload.cleaned_text
        print(f"[DEBUG] ingest_content:ingest_source complete cleaned_text_len={len(cleaned_text)}")
        text_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

        top_corrections = []
        if payload.correction_annotations:
            top_corrections = payload.correction_annotations.splitlines()[:5]
        if top_corrections:
            print(
                "[OBSERVE] ingest_content:top_transcript_corrections "
                f"content_id={content_id} corrections={json.dumps(top_corrections)}"
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

        print("[DEBUG] ingest_content:calling create_question_set")
        await create_question_set(
            session=session,
            content_id=content_id,
            cleaned_text=cleaned_text,
            correction_hints=payload.correction_annotations,
            kind=models.QuestionSetKind.scheduled,
        )

        print("[DEBUG] ingest_content:create_question_set complete")
        crud.set_content_ready(session, content)
        crud.init_schedule_state(session, content_id, datetime.utcnow() + timedelta(days=1))
        print(f"[DEBUG] ingest_content:ready content_id={content_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"[DEBUG] ingest_content:exception content_id={content_id} error={exc}")
        traceback.print_exc()
        session.rollback()
        crud.set_content_error(session, content, str(exc))
        print(f"[DEBUG] ingest_content:error persisted content_id={content_id}")
    return content

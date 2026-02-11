from datetime import datetime, timedelta
import hashlib
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
    print(f"[DEBUG] ingest_content:created content_id={content.id} status={content.status}")
    try:
        print("[DEBUG] ingest_content:calling ingest_source")
        cleaned_text = await ingest_source(source_type, url)
        print(f"[DEBUG] ingest_content:ingest_source complete cleaned_text_len={len(cleaned_text)}")
        text_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
        content_text = models.ContentText(
            content_id=content.id,
            cleaned_text=cleaned_text,
            text_hash=text_hash,
        )
        session.add(content_text)
        session.commit()

        print("[DEBUG] ingest_content:calling create_question_set")
        await create_question_set(
            session=session,
            content_id=content.id,
            cleaned_text=cleaned_text,
            kind=models.QuestionSetKind.scheduled,
        )

        print("[DEBUG] ingest_content:create_question_set complete")
        crud.set_content_ready(session, content)
        crud.init_schedule_state(session, content.id, datetime.utcnow() + timedelta(days=1))
        print(f"[DEBUG] ingest_content:ready content_id={content.id}")
    except Exception as exc:  # noqa: BLE001
        print(f"[DEBUG] ingest_content:exception content_id={content.id} error={exc}")
        traceback.print_exc()
        crud.set_content_error(session, content, str(exc))
        print(f"[DEBUG] ingest_content:error persisted content_id={content.id}")
    return content

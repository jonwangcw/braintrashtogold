from datetime import datetime, timedelta
import hashlib

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
    content = crud.create_content(session, title, models.ContentType(source_type), url)
    try:
        cleaned_text = await ingest_source(source_type, url)
        text_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
        content_text = models.ContentText(
            content_id=content.id,
            cleaned_text=cleaned_text,
            text_hash=text_hash,
        )
        session.add(content_text)
        session.commit()

        await create_question_set(
            session=session,
            content_id=content.id,
            cleaned_text=cleaned_text,
            kind=models.QuestionSetKind.scheduled,
        )

        crud.set_content_ready(session, content)
        crud.init_schedule_state(session, content.id, datetime.utcnow() + timedelta(days=1))
    except Exception as exc:  # noqa: BLE001
        crud.set_content_error(session, content, str(exc))
    return content

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db import crud, models
from app.ingest.router import ingest_source


async def ingest_content(
    session: Session, title: str, source_type: str, url: str
) -> models.Content:
    content = crud.create_content(session, title, models.ContentType(source_type), url)
    try:
        cleaned_text = await ingest_source(source_type, url)
        content_text = models.ContentText(
            content_id=content.id,
            cleaned_text=cleaned_text,
            text_hash=str(hash(cleaned_text)),
        )
        session.add(content_text)
        crud.set_content_ready(session, content)
        crud.init_schedule_state(session, content.id, datetime.utcnow() + timedelta(days=1))
    except Exception as exc:  # noqa: BLE001
        crud.set_content_error(session, content, str(exc))
    return content

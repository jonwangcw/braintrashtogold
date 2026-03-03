import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.engine import Base, SessionLocal, engine, ensure_schema_compatibility
from app.db import models
from app.services.content_service import ingest_content
from app.services.quiz_service import (
    complete_practice_quiz_attempt,
    complete_scheduled_quiz_attempt,
    create_quiz_attempt,
    get_quiz_attempt,
)


Base.metadata.create_all(bind=engine)
ensure_schema_compatibility()

def configure_windows_event_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


configure_windows_event_loop_policy()


def should_suppress_asyncio_write_send_assertion(context: dict) -> bool:
    message = str(context.get("message", ""))
    if "_SelectorSocketTransport._write_send" not in message:
        return False

    exc = context.get("exception")
    if not isinstance(exc, AssertionError):
        return False

    return "Data should not be empty" in str(exc)


def install_asyncio_exception_filter() -> None:
    loop = asyncio.get_event_loop()
    previous_handler = loop.get_exception_handler()

    def _handler(loop_obj, context):
        if should_suppress_asyncio_write_send_assertion(context):
            return
        if previous_handler is not None:
            previous_handler(loop_obj, context)
        else:
            loop_obj.default_exception_handler(context)

    loop.set_exception_handler(_handler)


install_asyncio_exception_filter()

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")


templates = Jinja2Templates(directory="app/ui/templates")


def _parse_json_list(raw_value: str | None) -> list:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _build_concepts_for_content(content: models.Content) -> list[dict]:
    concepts: list[dict] = []
    question_sets = sorted(
        content.question_sets,
        key=lambda qs: qs.generated_at,
        reverse=True,
    )
    if not question_sets:
        return concepts

    latest_questions = sorted(question_sets[0].questions, key=lambda item: item.question_index)
    for question in latest_questions:
        key_points = _parse_json_list(question.key_points_json)
        concept_name = key_points[0] if key_points else f"Concept {question.question_index + 1}"
        concepts.append(
            {
                "concept_id": question.id,
                "concept_name": concept_name,
                "prompt": question.prompt,
                "question_type": question.question_type,
                "key_points": key_points,
                "sources": _parse_json_list(question.sources_json),
            }
        )
    return concepts


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with SessionLocal() as session:
        contents = session.query(models.Content).order_by(models.Content.created_at.desc()).all()
    return templates.TemplateResponse("index.html", {"request": request, "contents": contents})


@app.get("/content/{content_id}", response_class=HTMLResponse)
def content_detail(request: Request, content_id: int):
    with SessionLocal() as session:
        content = session.execute(
            select(models.Content)
            .where(models.Content.id == content_id)
            .options(selectinload(models.Content.text), selectinload(models.Content.schedule_state), selectinload(models.Content.question_sets).selectinload(models.QuestionSet.questions))
        ).scalars().first()
    concepts = [] if content is None else _build_concepts_for_content(content)
    return templates.TemplateResponse(
        "content_detail.html", {"request": request, "content": content, "concepts": concepts}
    )


@app.get("/concept-review/due", response_class=HTMLResponse)
def due_concept_reviews(request: Request):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with SessionLocal() as session:
        due_contents = session.execute(
            select(models.Content)
            .join(models.ScheduleState, models.ScheduleState.content_id == models.Content.id)
            .where(models.ScheduleState.is_terminated.is_(False), models.ScheduleState.next_due_at.is_not(None), models.ScheduleState.next_due_at <= now)
            .options(selectinload(models.Content.schedule_state), selectinload(models.Content.question_sets).selectinload(models.QuestionSet.questions))
            .order_by(models.ScheduleState.next_due_at.asc())
        ).scalars().all()

    due_items = []
    for content in due_contents:
        concepts = _build_concepts_for_content(content)
        due_items.append({"content": content, "concept_count": len(concepts), "first_concept_id": concepts[0]["concept_id"] if concepts else None})

    return templates.TemplateResponse(
        "concept_due_list.html",
        {"request": request, "due_items": due_items},
    )


@app.get("/concept-review/{content_id}/{concept_id}", response_class=HTMLResponse)
def concept_probe_view(request: Request, content_id: int, concept_id: int):
    with SessionLocal() as session:
        content = session.execute(
            select(models.Content)
            .where(models.Content.id == content_id)
            .options(selectinload(models.Content.schedule_state), selectinload(models.Content.question_sets).selectinload(models.QuestionSet.questions), selectinload(models.Content.text))
        ).scalars().first()

    concepts = [] if content is None else _build_concepts_for_content(content)
    selected_concept = next((concept for concept in concepts if concept["concept_id"] == concept_id), None)
    return templates.TemplateResponse(
        "concept_probe.html",
        {
            "request": request,
            "content": content,
            "concept": selected_concept,
            "schedule_state": None if content is None else content.schedule_state,
        },
    )


@app.post("/concept-review/submit")
def submit_concept_probe(content_id: int = Form(...), concept_id: int = Form(...), probe_id: int = Form(...), comfort_level: int = Form(...)):
    if comfort_level < 0 or comfort_level > 3:
        raise ValueError("comfort_level must be between 0 and 3")

    redirect_url = f"/concept-review/{content_id}/{concept_id}?submitted=1&probe_id={probe_id}&comfort_level={comfort_level}"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/ingest")
async def ingest(
    url: str = Form(""),
    title: str = Form(""),
    pdf_file: UploadFile | None = File(default=None),
):
    if pdf_file and pdf_file.filename:
        suffix = Path(pdf_file.filename).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await pdf_file.read())
            temp_path = temp_file.name

        try:
            source_label = f"local://{pdf_file.filename}"
            if not title:
                title = pdf_file.filename
            print(f"[DEBUG] /ingest called local_pdf={source_label} title={title}")
            with SessionLocal() as session:
                result = await ingest_content(
                    session,
                    title,
                    source=temp_path,
                    source_url=source_label,
                    source_type="pdf",
                )
                print(
                    f"[DEBUG] /ingest completed content_id={result.id} status={result.status} error={result.error_message}"
                )
        finally:
            Path(temp_path).unlink(missing_ok=True)
        return RedirectResponse(url="/", status_code=303)

    if not url:
        raise ValueError("URL is required when no PDF file is uploaded")

    if not title:
        title = url
    print(f"[DEBUG] /ingest called url={url} title={title}")
    with SessionLocal() as session:
        result = await ingest_content(session, title, source=url)
        print(
            f"[DEBUG] /ingest completed content_id={result.id} status={result.status} error={result.error_message}"
        )
    return RedirectResponse(url="/", status_code=303)


@app.get("/quiz/{content_id}/scheduled", response_class=HTMLResponse)
async def scheduled_quiz(request: Request, content_id: int):
    with SessionLocal() as session:
        question_set = session.execute(
            select(models.QuestionSet)
            .where(
                models.QuestionSet.content_id == content_id,
                models.QuestionSet.kind == models.QuestionSetKind.scheduled,
            )
            .order_by(models.QuestionSet.generated_at.desc())
            .options(selectinload(models.QuestionSet.questions))
        ).scalars().first()
        attempt = create_quiz_attempt(session, content_id, models.QuizAttemptKind.scheduled)

    questions = [] if question_set is None else sorted(question_set.questions, key=lambda q: q.question_index)
    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "content_id": content_id,
            "kind": "scheduled",
            "questions": questions,
            "quiz_attempt_id": attempt.id,
            "show_comfort_control": True,
        },
    )


@app.get("/quiz/{content_id}/practice", response_class=HTMLResponse)
async def practice_quiz(request: Request, content_id: int):
    with SessionLocal() as session:
        attempt = create_quiz_attempt(session, content_id, models.QuizAttemptKind.practice)
    return templates.TemplateResponse(
        "quiz.html",
        {"request": request, "content_id": content_id, "kind": "practice", "questions": [], "quiz_attempt_id": attempt.id, "show_comfort_control": False},
    )


@app.post("/quiz/{quiz_attempt_id}/complete", response_class=HTMLResponse)
async def complete_quiz(
    request: Request,
    quiz_attempt_id: int,
    comfort_rating: int | None = Form(default=None),
):
    with SessionLocal() as session:
        existing_attempt = get_quiz_attempt(session, quiz_attempt_id)
        if existing_attempt is None:
            return RedirectResponse(url="/", status_code=303)

        if existing_attempt.kind == models.QuizAttemptKind.scheduled:
            if comfort_rating is None:
                raise ValueError("comfort_rating is required for scheduled quizzes")
            attempt = complete_scheduled_quiz_attempt(session, quiz_attempt_id, comfort_rating=comfort_rating)
        else:
            attempt = complete_practice_quiz_attempt(session, quiz_attempt_id)

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "quiz_attempt_id": quiz_attempt_id,
            "submitted_at": attempt.submitted_at,
            "comfort_rating": attempt.comfort_rating if attempt.kind == models.QuizAttemptKind.scheduled else None,
        },
    )

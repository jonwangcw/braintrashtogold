import asyncio
import sys
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.engine import Base, SessionLocal, engine
from app.db import models
from app.services.content_service import ingest_content
from app.services.quiz_service import (
    complete_practice_quiz_attempt,
    complete_scheduled_quiz_attempt,
    create_quiz_attempt,
    get_quiz_attempt,
)


Base.metadata.create_all(bind=engine)

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
            .options(selectinload(models.Content.text))
        ).scalars().first()
    return templates.TemplateResponse(
        "content_detail.html", {"request": request, "content": content}
    )


@app.post("/ingest")
async def ingest(source_type: str = Form(...), url: str = Form(...), title: str = Form("")):
    if not title:
        title = url
    print(f"[DEBUG] /ingest called source_type={source_type} url={url} title={title}")
    with SessionLocal() as session:
        result = await ingest_content(session, title, source_type, url)
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
        },
    )


@app.get("/quiz/{content_id}/practice", response_class=HTMLResponse)
async def practice_quiz(request: Request, content_id: int):
    with SessionLocal() as session:
        attempt = create_quiz_attempt(session, content_id, models.QuizAttemptKind.practice)
    return templates.TemplateResponse(
        "quiz.html",
        {"request": request, "content_id": content_id, "kind": "practice", "questions": [], "quiz_attempt_id": attempt.id},
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

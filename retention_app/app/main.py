import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.engine import Base, SessionLocal, engine, ensure_schema_compatibility
from app.db import crud, models
from app.config import settings
from app.scheduling.scheduler import ReminderScheduler
from app.services.content_service import ingest_content
from app.services.quiz_service import (
    complete_practice_quiz_attempt,
    complete_scheduled_quiz_attempt,
    create_quiz_attempt,
    get_quiz_attempt,
)
from app.services.review_service import (
    fetch_due_concepts,
    generate_or_reuse_probe,
    submit_concept_review,
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.enable_system_notifications or settings.enable_email_reminders:
        scheduler = ReminderScheduler(SessionLocal)
        scheduler.start()
        try:
            yield
        finally:
            scheduler.shutdown()
    else:
        yield


app = FastAPI(lifespan=lifespan)

def _get_current_user(request: Request, session) -> models.User | None:
    username = request.cookies.get("username")
    if not username:
        return None
    return session.query(models.User).filter(models.User.username == username).first()


_BLOOM_ORDER = ["remember", "understand", "apply", "analyze", "evaluate", "create"]


def _split_questions(questions: list, ceiling: str) -> tuple[list, list]:
    ceiling_idx = _BLOOM_ORDER.index(ceiling) if ceiling in _BLOOM_ORDER else 1
    scheduled = [q for q in questions if q.question_type in _BLOOM_ORDER[: ceiling_idx + 1]]
    optional = [q for q in questions if q.question_type in _BLOOM_ORDER[ceiling_idx + 1 :]]
    return scheduled, optional


def _ensure_legacy_quiz_enabled() -> None:
    if not settings.enable_legacy_quizzes:
        raise HTTPException(
            status_code=410,
            detail="Legacy content-level quizzes are deprecated. Use /reviews/* and /concepts/* endpoints.",
        )

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


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(username: str = Form(...)):
    username = username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    with SessionLocal() as session:
        crud.get_or_create_user(session, username)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("username", username, max_age=365 * 24 * 3600, httponly=True)
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("username")
    return response


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with SessionLocal() as session:
        user = _get_current_user(request, session)
        if user is None:
            return RedirectResponse(url="/login", status_code=303)
        contents = session.query(models.Content).filter(
            models.Content.user_id == user.id
        ).order_by(models.Content.created_at.desc()).all()
    return templates.TemplateResponse("index.html", {"request": request, "contents": contents, "username": user.username})


@app.get("/content/{content_id}", response_class=HTMLResponse)
def content_detail(request: Request, content_id: int):
    with SessionLocal() as session:
        user = _get_current_user(request, session)
        if user is None:
            return RedirectResponse(url="/login", status_code=303)
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
        user = _get_current_user(request, session)
        if user is None:
            return RedirectResponse(url="/login", status_code=303)
        due_contents = session.execute(
            select(models.Content)
            .join(models.ScheduleState, models.ScheduleState.content_id == models.Content.id)
            .where(models.ScheduleState.is_terminated.is_(False), models.ScheduleState.next_due_at.is_not(None), models.ScheduleState.next_due_at <= now, models.Content.user_id == user.id)
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
        user = _get_current_user(request, session)
        if user is None:
            return RedirectResponse(url="/login", status_code=303)
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
    request: Request,
    url: str = Form(""),
    title: str = Form(""),
    pdf_file: UploadFile | None = File(default=None),
):
    with SessionLocal() as _auth_session:
        user = _get_current_user(request, _auth_session)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    user_id = user.id

    if pdf_file and pdf_file.filename:
        suffix = Path(pdf_file.filename).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await pdf_file.read())
            temp_path = temp_file.name

        try:
            source_label = f"local://{pdf_file.filename}"
            print(f"[DEBUG] /ingest called local_pdf={source_label} title={title!r}")
            with SessionLocal() as session:
                result = await ingest_content(
                    session,
                    title,
                    source=temp_path,
                    source_url=source_label,
                    source_type="pdf",
                    user_id=user_id,
                )
                print(
                    f"[DEBUG] /ingest completed content_id={result.id} status={result.status} error={result.error_message}"
                )
        finally:
            Path(temp_path).unlink(missing_ok=True)
        return RedirectResponse(url="/", status_code=303)

    if not url:
        raise ValueError("URL is required when no PDF file is uploaded")

    print(f"[DEBUG] /ingest called url={url} title={title!r}")
    with SessionLocal() as session:
        result = await ingest_content(session, title, source=url, user_id=user_id)
        print(
            f"[DEBUG] /ingest completed content_id={result.id} status={result.status} error={result.error_message}"
        )
    return RedirectResponse(url="/", status_code=303)




@app.get("/concepts")
def list_concepts(limit: int = 100):
    with SessionLocal() as session:
        concepts = session.execute(select(models.Concept).order_by(models.Concept.created_at.desc()).limit(limit)).scalars().all()
    return [
        {
            "id": concept.id,
            "content_id": concept.content_id,
            "title": concept.title,
            "summary": concept.summary,
            "created_at": concept.created_at,
        }
        for concept in concepts
    ]


@app.get("/concepts/{concept_id}")
def get_concept(concept_id: int):
    with SessionLocal() as session:
        concept = session.get(models.Concept, concept_id)
        if concept is None:
            raise HTTPException(status_code=404, detail="Concept not found")

        schedule = session.get(models.ConceptSchedule, concept_id)
        probe = generate_or_reuse_probe(session, concept_id)

    return {
        "id": concept.id,
        "content_id": concept.content_id,
        "title": concept.title,
        "summary": concept.summary,
        "schedule": None
        if schedule is None
        else {
            "step_index": schedule.step_index,
            "next_due_at": schedule.next_due_at,
            "is_terminated": schedule.is_terminated,
            "last_score": schedule.last_score,
        },
        "probe": {
            "id": probe.id,
            "prompt": probe.prompt,
            "expected_answer": probe.expected_answer,
            "status": probe.status,
        },
    }


@app.get("/reviews/due")
def due_reviews(limit: int = 20):
    with SessionLocal() as session:
        concepts = fetch_due_concepts(session, limit=limit)
        payload = []
        for concept in concepts:
            probe = generate_or_reuse_probe(session, concept.id)
            schedule = session.get(models.ConceptSchedule, concept.id)
            payload.append(
                {
                    "concept_id": concept.id,
                    "title": concept.title,
                    "probe": {
                        "probe_id": probe.id,
                        "prompt": probe.prompt,
                        "expected_answer": probe.expected_answer,
                    },
                    "next_due_at": schedule.next_due_at if schedule else None,
                    "step_index": schedule.step_index if schedule else None,
                }
            )
    return payload


class ReviewSubmitPayload(BaseModel):
    concept_id: int
    probe_id: int
    self_comfort: int
    correctness: float | None = None
    response_text: str | None = None


@app.post("/reviews/submit")
def submit_review(payload: ReviewSubmitPayload):
    with SessionLocal() as session:
        try:
            event, schedule = submit_concept_review(
                session,
                concept_id=payload.concept_id,
                probe_id=payload.probe_id,
                self_comfort=payload.self_comfort,
                correctness=payload.correctness,
                response_text=payload.response_text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(
        {
            "review_event_id": event.id,
            "concept_id": event.concept_id,
            "probe_id": event.probe_id,
            "score": event.score,
            "next_due_at": schedule.next_due_at.isoformat() if schedule.next_due_at else None,
            "step_index": schedule.step_index,
            "is_terminated": schedule.is_terminated,
        }
    )


@app.get("/quiz/{content_id}/scheduled", response_class=HTMLResponse)
async def scheduled_quiz(request: Request, content_id: int):
    _ensure_legacy_quiz_enabled()
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
    scheduled_qs, optional_qs = _split_questions(questions, settings.scheduled_bloom_ceiling)
    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "content_id": content_id,
            "kind": "scheduled",
            "scheduled_questions": scheduled_qs,
            "optional_questions": optional_qs,
            "quiz_attempt_id": attempt.id,
            "show_comfort_control": True,
        },
    )


@app.get("/quiz/{content_id}/practice", response_class=HTMLResponse)
async def practice_quiz(request: Request, content_id: int):
    _ensure_legacy_quiz_enabled()
    with SessionLocal() as session:
        attempt = create_quiz_attempt(session, content_id, models.QuizAttemptKind.practice)
    return templates.TemplateResponse(
        "quiz.html",
        {"request": request, "content_id": content_id, "kind": "practice", "scheduled_questions": [], "optional_questions": [], "quiz_attempt_id": attempt.id, "show_comfort_control": False},
    )


@app.post("/quiz/{quiz_attempt_id}/complete", response_class=HTMLResponse)
async def complete_quiz(
    request: Request,
    quiz_attempt_id: int,
    comfort_rating: int | None = Form(default=None),
):
    _ensure_legacy_quiz_enabled()
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

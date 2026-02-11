import asyncio
import sys
from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.engine import Base, SessionLocal, engine
from app.db import models
from app.services.content_service import ingest_content


Base.metadata.create_all(bind=engine)

def configure_windows_event_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


configure_windows_event_loop_policy()

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
        content = session.get(models.Content, content_id)
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
    return templates.TemplateResponse(
        "quiz.html", {"request": request, "content_id": content_id, "kind": "scheduled"}
    )


@app.get("/quiz/{content_id}/practice", response_class=HTMLResponse)
async def practice_quiz(request: Request, content_id: int):
    return templates.TemplateResponse(
        "quiz.html", {"request": request, "content_id": content_id, "kind": "practice"}
    )


@app.post("/quiz/{quiz_attempt_id}/submit", response_class=HTMLResponse)
async def submit_quiz(request: Request, quiz_attempt_id: int):
    return templates.TemplateResponse(
        "results.html",
        {"request": request, "quiz_attempt_id": quiz_attempt_id, "submitted_at": datetime.utcnow()},
    )

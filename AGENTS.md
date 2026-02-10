# IMPLEMENTATION.md

## Goal

Build a local web app (“education retention app”) that:

1. Ingests content from:
   - YouTube video URLs (audio extracted via `yt-dlp`)
   - Podcast RSS feeds (XML) → enclosure audio URLs
   - PDFs (text-based only)
   - Webpages (readability extraction)
   - Web-hosted PDFs (detect and process like PDFs)
2. If audio/video, transcribe with hosted Whisper-style transcription API and produce cleaned text.
3. Use OpenRouter (API key in `.env` as `OPENROUTER_API_KEY`) to generate 10 questions:
   - 5 recall questions
   - 5 explain-in-own-words questions
   - Each question includes supporting **source quotes/snippets** from the cleaned text.
4. Quiz flow:
   - User answers questions.
   - LLM grades each answer: **1.0 / 0.5 / 0.0**
   - Total score saved; affects next scheduled quiz time (until schedule ends).
5. Scheduling:
   - Default v1 schedule steps: `+1d, +1d, +1d, +3d, +5d, +7d, +7d, +14d` (relative to the last **scheduled** quiz completion)
   - Score adjustment:
     - If score >= 8: add **+2 days** to the next interval **(not skipping steps)**, **except** this rule does not apply to the first three daily quizzes.
     - If score <= 5: reset schedule back to step 0 and regenerate a fresh question set.
     - If 5 < score < 8: no change.
   - **Termination:** after completing the final scheduled step (`+14d`), the schedule **terminates** and the item becomes **on-demand only** (no further scheduled reminders).
6. User can request an **on-demand practice quiz** anytime:
   - Generates a fresh set of questions.
   - Graded and shown to user.
   - Does **not** alter the schedule (and is the only mode after schedule termination).

Deliverables:
- Working local web app
- Persistent content library + quiz history
- Email reminders + system notifications when a scheduled quiz is due (until schedule terminates)
- Clean, testable architecture (ingest → transcribe/extract → question-gen → quiz → grading → scheduling)

---

## Non-goals (v1)

- Scanned/image PDFs: return “invalid media (scanned PDF not supported)”
- Spotify ingestion
- Multi-user accounts
- Mobile client

---

## Tech stack

- **Python 3.11+**
- Web framework: **FastAPI** + Jinja2 templates (server-rendered UI for v1)
- Background jobs / scheduling: **APScheduler**
- DB: **SQLite** via **SQLAlchemy** (or SQLModel) for ORM
- Migrations: **Alembic**
- Ingestion:
  - YouTube audio: `yt-dlp`
  - RSS: `feedparser`
  - Webpage extraction: `trafilatura` (preferred) or `readability-lxml` + `beautifulsoup4`
  - PDF extraction: `pypdf` (text-only)
- Audio processing: `ffmpeg` (invoked by `yt-dlp` or directly if needed)
- Transcription: OpenAI **audio transcription endpoint** (hosted)
- LLM calls: OpenRouter (`httpx` recommended)
- Notifications:
  - Email via SMTP (`aiosmtplib` or `smtplib`)
  - System notifications: `plyer` (cross-platform) or OS-specific library
- Testing: `pytest`

---

## Repository structure

```
retention_app/
  app/
    main.py                 # FastAPI app entrypoint
    config.py               # env loading, settings
    db/
      engine.py             # SQLAlchemy engine/session
      models.py             # ORM models
      migrations/           # Alembic
      crud.py               # DB operations
    ingest/
      router.py             # ingress dispatcher: youtube/rss/pdf/web/html
      youtube.py
      rss.py
      pdf.py
      web.py
      common.py             # shared helpers + validation
    processing/
      clean_text.py         # normalization, chunking
      chunking.py           # chunk + snippet extraction
      transcribe.py         # hosted transcription wrapper
    llm/
      openrouter_client.py
      prompts.py            # prompt templates
      schemas.py            # Pydantic models for JSON outputs
      question_gen.py
      grading.py
    scheduling/
      strategy_base.py      # interface for spacing strategies
      strategy_v1.py        # your ad hoc schedule
      scheduler.py          # APScheduler integration
      notifications.py      # email + system notifications
    ui/
      templates/
        index.html
        content_detail.html
        quiz.html
        results.html
      static/
        styles.css
    services/
      content_service.py
      quiz_service.py
  tests/
    test_ingest_youtube.py
    test_ingest_rss.py
    test_pdf_text_only.py
    test_web_readability.py
    test_question_schema_validation.py
    test_grading_schema_validation.py
    test_scheduler_v1.py
  .env.example
  IMPLEMENTATION.md
  README.md
  pyproject.toml
```

---

## Environment variables (.env)

Create `.env` (gitignored) and `.env.example` (committed).

Required:
- `OPENROUTER_API_KEY=...`
- `OPENROUTER_MODEL=...` (e.g., `openai/gpt-4o-mini` or similar)
- `OPENAI_API_KEY=...` (for transcription)

Email reminders (required if “quiz pushed” means email):
- `SMTP_HOST=...`
- `SMTP_PORT=587`
- `SMTP_USERNAME=...`
- `SMTP_PASSWORD=...`
- `EMAIL_FROM=...`
- `EMAIL_TO=...` (single local user)

System notifications:
- `ENABLE_SYSTEM_NOTIFICATIONS=true|false`

Operational:
- `APP_BASE_URL=http://localhost:8000`
- `TIMEZONE=America/New_York`

---

## Data model (SQLite)

### Core tables

**contents**
- `id` (PK)
- `title` (string)
- `content_type` (enum: youtube, rss_episode, pdf, webpage)
- `source_url` (string)
- `created_at` (datetime)
- `status` (enum: pending, ready, error)
- `error_message` (text nullable)

**content_text**
- `content_id` (PK/FK -> contents.id)
- `cleaned_text` (long text)
- `text_hash` (string)  # for dedupe/repro
- `created_at`

**question_sets**
- `id` (PK)
- `content_id` (FK)
- `kind` (enum: scheduled, practice)
- `generated_at`
- `generator_model` (string)
- `generation_prompt_version` (string)

**questions**
- `id` (PK)
- `question_set_id` (FK)
- `question_index` (0..9)
- `question_type` (enum: recall, explain)
- `prompt` (text)
- `expected_answer` (text)
- `key_points_json` (JSON text)  # list[str]
- `sources_json` (JSON text)     # list[{quote, start_char, end_char}]
- `created_at`

**quiz_attempts**
- `id` (PK)
- `content_id` (FK)
- `question_set_id` (FK)
- `kind` (scheduled, practice)
- `started_at`
- `submitted_at`
- `total_score` (float)
- `grader_model` (string)
- `grading_prompt_version` (string)

**answers**
- `id` (PK)
- `quiz_attempt_id` (FK)
- `question_id` (FK)
- `user_answer` (text)
- `score` (float: 0, 0.5, 1)
- `feedback` (text)  # short explanation
- `graded_at`

**schedule_state**
- `content_id` (PK/FK)
- `step_index` (int)      # 0..7 for v1
- `next_due_at` (datetime nullable)  # null when terminated
- `last_scheduled_quiz_at` (datetime nullable)
- `last_score` (float nullable)
- `is_terminated` (bool)  # when true: on-demand only

**notifications**
- `id` (PK)
- `content_id` (FK)
- `kind` (email, system)
- `scheduled_for` (datetime)
- `sent_at` (datetime nullable)
- `status` (pending, sent, failed)
- `error` (text nullable)

Notes:
- When `is_terminated = true`, set `next_due_at = NULL` and do not schedule/send reminders.

---

## Ingestion pipeline

### Ingest dispatcher

`POST /ingest` accepts:
- `{ "source_type": "youtube", "url": "..." }`
- `{ "source_type": "rss", "url": "..." }` then UI lets user pick an episode
- `{ "source_type": "pdf", "url": "..." }` or upload file
- `{ "source_type": "webpage", "url": "..." }`

Dispatcher steps:
1. Validate URL
2. Fetch/parse/download
3. Produce a **raw text** or **audio file**
4. Convert to cleaned text (transcribe if audio)
5. Store in DB
6. Initialize schedule_state for this content:
   - `step_index = 0`
   - `next_due_at = now + 1 day`
   - `is_terminated = false`

---

## YouTube ingestion (`ingest/youtube.py`)

1. Use `yt-dlp` to download best audio to a temp directory.
2. Enforce max length 1 hour:
   - if duration > 60min: reject.
3. Transcribe with hosted transcription.
4. Clean and store.

---

## Podcast RSS ingestion (`ingest/rss.py`)

1. Parse RSS with `feedparser`.
2. Display episodes with title + pubDate.
3. User selects episode:
   - download enclosure audio URL
   - enforce max length 1 hour (best-effort)
4. Transcribe and store.

---

## PDF ingestion (`ingest/pdf.py`)

1. Confirm PDF is text-based:
   - extract text from first N pages; if near-empty → treat as scanned and return invalid.
2. Extract full text with `pypdf`.
3. Clean and store.

---

## Webpage ingestion (`ingest/web.py`)

1. Fetch HTML.
2. Use readability extractor (`trafilatura` preferred).
3. Clean and store.
4. If URL returns PDF content-type or ends with `.pdf`, route to PDF ingestion.

---

## Transcription (hosted)

`processing/transcribe.py`:

- Wrap OpenAI transcription call.
- Return raw transcript text.
- Hook for future chunking (not required under 1 hour, but keep interface chunk-friendly).

---

## Text cleaning + chunking

`processing/clean_text.py`:
- normalize whitespace
- remove boilerplate (basic heuristics)
- preserve paragraph breaks
- output `cleaned_text`

`processing/chunking.py`:
- split cleaned_text into chunks for LLM input
- maintain char offsets:
  - chunks with `start_char`, `end_char`, `text`

---

## LLM integration (OpenRouter)

### Question generation strict JSON schema (Pydantic)

`llm/schemas.py`:

**QuestionSetOutput**
- `content_id: str`
- `questions: list[QuestionOutput]` (length == 10)

**QuestionOutput**
- `question_id: str`
- `question_type: Literal["recall","explain"]`
- `prompt: str`
- `expected_answer: str`
- `key_points: list[str]`  (non-empty)
- `sources: list[SourceSnippet]` (>=1)

**SourceSnippet**
- `quote: str` (<= 300 chars recommended)
- `start_char: int`
- `end_char: int`

Validation:
- exactly 10 questions
- exactly 5 recall + 5 explain
- offsets should match substring in cleaned_text (normalize whitespace for comparison)
- basic dedupe check on prompts

### Grading schema (Pydantic)

**GradingOutput**
- `quiz_attempt_id: str`
- `results: list[GradedAnswer]`

**GradedAnswer**
- `question_id: str`
- `score: Literal[0, 0.5, 1]`
- `feedback: str` (1–3 sentences)

Grading prompt:
- include prompt + expected_answer + key_points + source quotes + user answer
- temperature = 0

---

## Quiz flow

### Scheduled quiz
Due when:
- `schedule_state.is_terminated = false` AND
- `schedule_state.next_due_at <= now`

Flow:
1. Generate a **scheduled** question_set for this attempt.
2. User answers in UI.
3. Grade with LLM.
4. Save results, update schedule_state, possibly terminate.

### Practice quiz (on-demand)
Always allowed:
1. Generate a **practice** question_set fresh.
2. User answers.
3. Grade and show results.
4. Store attempt + answers, but **do not** modify schedule_state.

---

## Scheduling design (pluggable strategy)

### Strategy interface

`scheduling/strategy_base.py`:

`next_state(step_index, last_completed_at, last_score, scheduled_attempt_count) -> ScheduleDecision`

Where `ScheduleDecision` contains:
- `next_due_at: datetime | None`
- `next_step_index: int`
- `terminate: bool`
- `reset_questions: bool`

### v1 Strategy (your schedule)

Schedule intervals by step_index:
- 0: +1 day
- 1: +1 day
- 2: +1 day
- 3: +3 days
- 4: +5 days
- 5: +7 days
- 6: +7 days
- 7: +14 days (FINAL step)

Rules:
- If last_score <= 5:
  - reset to step_index=0
  - next_due = now + 1 day
  - `reset_questions = True`
  - `terminate = False`
- Else:
  - base_interval = schedule[step_index]
  - if last_score >= 8 and scheduled_attempt_count >= 3:
    - base_interval += 2 days
  - next_due = last_completed_at + base_interval
  - next_step_index = step_index + 1
  - if next_step_index > 7:
    - terminate = True
    - next_due_at = None
  - else:
    - terminate = False
- On terminate:
  - set `is_terminated = true`, `next_due_at = NULL`

### Scheduler engine (APScheduler)

Every N minutes:
- query for due scheduled items
- create and send notifications (email + system)
- idempotent via `notifications` table

After schedule termination:
- stop checking/sending notifications for that content item.

---

## Notifications

### Email reminders
- Send once per due event
- Include content title + link to local app page

### System notifications
- Use `plyer` if enabled; fall back gracefully

---

## API routes (FastAPI)

- `GET /` — list content items + due status + terminated flag
- `GET /content/{content_id}` — content detail, history, next due, actions
- `POST /ingest` — start ingestion job
- `GET /ingest/rss/select?feed_url=...` — choose episode
- `GET /quiz/{content_id}/scheduled` — allowed only if due and not terminated
- `GET /quiz/{content_id}/practice` — always allowed
- `POST /quiz/{quiz_attempt_id}/submit` — grade, store, update schedule if scheduled

---

## Implementation order

1. Skeleton + settings + `.env.example`
2. SQLite models + Alembic migration
3. UI pages: list + content detail
4. Ingestion: webpage → PDF → YouTube → RSS
5. Cleaning + chunking
6. OpenRouter client + strict JSON parsing/validation
7. Question generation + storage
8. Quiz UI + grading + results
9. Strategy interface + v1 strategy + termination behavior
10. APScheduler + email + system notifications
11. Tests + smoke tests

---

## Testing plan (minimum)

- PDF scanned detection returns invalid
- YouTube duration cap rejects > 1 hour
- Readability extractor yields non-empty cleaned text
- Question JSON validates and has 5/5 split
- Quote offsets map into cleaned_text
- Grading JSON validates; score ∈ {0,0.5,1}
- Scheduler:
  - progresses steps
  - applies +2 days after first 3 scheduled attempts only
  - resets on <=5 and regenerates
  - terminates after final step and stops reminders

---

## SQL + SQLite primer (short)

### What SQL is
SQL is how you read/write relational tables.

Key operations:
- `SELECT` (read)
- `INSERT` (add)
- `UPDATE` (change)
- `DELETE` (remove)

Example:
```sql
SELECT id, title FROM contents ORDER BY created_at DESC;
```

### Why you still don’t need to “know SQL” right away
Use SQLAlchemy (ORM). You’ll interact with Python objects and let the ORM generate SQL.

SQLite is a local, single-file database (`app.db`)—perfect for a single-user local app.


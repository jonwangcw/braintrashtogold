# Retention App (Local)

This project is a local education retention app built with FastAPI + SQLite. It ingests content (YouTube, RSS, PDF, webpages), generates question sets via OpenRouter, and schedules recall quizzes.

## Quick start

1. Create a virtualenv and install dependencies:

```bash
pip install -e .
```
2. Copy `.env.example` to `.env` and fill in values (`OPENROUTER_API_KEY` required; local Whisper uses `WHISPER_MODEL`).
3. Run the app:

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000`.

## Development notes

- SQLite database file is created as `app.db` in the project root.
- Scheduling is handled by APScheduler and runs in-process.

## Testing

Run the test suite from the `retention_app` directory:

```bash
pytest
```

## Troubleshooting

### YouTube ingestion: JavaScript runtime warning/error

If `yt-dlp` prints a warning about missing JS runtime support (for example, `No supported JavaScript runtime could be found`), install a JS runtime such as **Node.js** or **Deno** and retry.

On some environments, YouTube extraction may fail without this runtime, and the app will set content status to `error` with the underlying message.


- Email reminders are disabled by default. Set `ENABLE_EMAIL_REMINDERS=true` and SMTP variables to enable them.

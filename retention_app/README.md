# Retention App

A self-hosted knowledge retention platform that ingests content from multiple sources, generates structured quiz questions using an LLM, and schedules spaced-repetition review sessions.

---

## Overview

The application runs a local web server and manages the full lifecycle from ingestion to review:

1. **Ingest** — submit a URL (YouTube video, podcast RSS feed, webpage, or web-hosted PDF) or upload a local PDF.
2. **Process** — audio is transcribed with Whisper, OCR is applied to video frames, and a corrected transcript is produced.
3. **Generate** — an LLM (via OpenRouter) generates quiz questions at all six levels of Bloom's Revised Taxonomy.
4. **Schedule** — a spaced-repetition scheduler determines when each item is next due for review, based on a comfort self-assessment after each quiz.
5. **Notify** — system notifications (and optionally email) alert when items are due.

---

## Features

- Multi-source ingestion: YouTube, podcast RSS, PDF (local or web), and general webpages
- Audio transcription via OpenAI Whisper with OCR-assisted correction
- LLM-based question generation covering all six Bloom's Taxonomy levels (remember, understand, apply, analyze, evaluate, create)
- Comfort-rated spaced repetition with automatic rescheduling
- Per-user content libraries with cookie-based sessions (no passwords)
- System tray notifications via plyer (Windows PowerShell fallback included)
- Optional email reminders via SMTP
- Docker support with volume-mounted persistence
- CI via GitHub Actions

---

## Requirements

| Dependency | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| Node.js | Required by yt-dlp for YouTube extraction |
| ffmpeg | Audio decoding for Whisper transcription |
| Tesseract OCR | Text extraction from video frames |

---

## Installation

```bash
pip install -e .
```

Copy the example environment file and fill in the required values:

```bash
cp .env.example .env
```

At minimum, set `OPENROUTER_API_KEY`.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | API key for LLM question generation |
| `WHISPER_MODEL` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`) |
| `ENABLE_SYSTEM_NOTIFICATIONS` | `false` | Enable desktop notifications for due items |
| `ENABLE_EMAIL_REMINDERS` | `false` | Enable email reminders for due items |
| `SMTP_HOST` | — | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | — | SMTP authentication username |
| `SMTP_PASSWORD` | — | SMTP authentication password |
| `EMAIL_FROM` | — | Sender address for email reminders |
| `EMAIL_TO` | — | Recipient address for email reminders |
| `APP_BASE_URL` | `http://localhost:8000` | Base URL included in notification links |
| `TIMEZONE` | *(auto-detected)* | IANA timezone string for the scheduler (e.g. `America/New_York`) |
| `SCHEDULED_BLOOM_CEILING` | `understand` | Highest Bloom level classified as required in a scheduled quiz |
| `QUESTIONS_PER_BLOOM_LEVEL` | `3` | Number of questions generated per Bloom level (total = level × 6) |

---

## Running

```bash
uvicorn app.main:app --reload
```

Navigate to `http://localhost:8000`.

### One-click launchers

| Platform | File |
|---|---|
| Windows | `Run_Retention_App.bat` |
| macOS / Linux | `Run_Retention_App.command` |

Both launchers create a `.venv`, install dependencies, copy `.env.example` to `.env` if needed, and start the server.

---

## Docker

```bash
docker compose up
```

The compose file mounts volumes for the SQLite database, generated artifacts, and the Whisper model cache. System notifications are disabled in the container.

---

## Testing

```bash
pytest
```

---

## Troubleshooting

### YouTube extraction fails with a JavaScript runtime warning

`yt-dlp` requires a JavaScript runtime for some YouTube content. Install [Node.js](https://nodejs.org) and ensure `node` is on your `PATH`.

### Tesseract not found

Install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) and ensure the binary is on your `PATH`. On Windows, the installer adds it automatically; on Linux, use `apt install tesseract-ocr`.

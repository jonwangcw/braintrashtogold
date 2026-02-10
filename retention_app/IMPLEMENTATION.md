# Implementation Notes

This repository contains the initial skeleton for the retention app described in `AGENTS.md`.

## Status

- FastAPI app with server-rendered UI templates.
- SQLite models and scheduling strategy skeleton.
- Ingestion/transcription/LLM hooks with placeholders for full pipelines.

## Next steps

- Implement full ingestion pipelines for YouTube/RSS/PDF/Web.
- Persist question sets and quiz attempts with proper CRUD layers.
- Add APScheduler job wiring and notification persistence.
- Add comprehensive tests per the testing plan.

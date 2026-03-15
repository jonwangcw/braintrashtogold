# Rot2Gold — Retention App

A personal spaced-repetition learning system. The user submits content (YouTube videos, PDFs, web pages, RSS/podcast episodes) and the app automatically generates Bloom's Taxonomy quiz questions, tracks concepts extracted from that content, and schedules review sessions using a spaced-repetition algorithm to maximise long-term retention.

---

## Directory structure

```
retention_app/
  app/                    # Main application
    db/                   # SQLAlchemy models, engine, CRUD helpers
    ingest/               # Source-specific ingestion (RSS stub; YouTube via yt-dlp + Whisper)
    llm/                  # LLM client wrappers and prompt logic
    processing/           # Text cleaning utilities
    scheduling/           # Spaced-repetition scheduling logic
    services/             # Higher-level orchestration (stub)
  finetune/               # ML pipeline — see finetune/CLAUDE.md for full detail
    scripts/              # 01_collect_wikipedia → 09_evaluate, export_checkpoint
    data/                 # Training/eval JSONL, chunks, eval results
    checkpoints/          # LoRA adapter checkpoints per epoch
    merged_model/         # Current merged 16-bit model ready for GGUF export
  pyproject.toml
  CLAUDE.md               # This file
```

---

## App stack

| Layer | Library |
|---|---|
| Web framework | FastAPI + Uvicorn |
| ORM / DB | SQLAlchemy 2.0, Alembic migrations, SQLite |
| Validation | Pydantic v2 |
| Scheduling | APScheduler |
| Notifications | aiosmtplib (email), plyer (system) |
| HTTP client | httpx |
| Content fetch | trafilatura, readability-lxml, BeautifulSoup4 |
| YouTube | yt-dlp (download), openai-whisper (transcription) |
| PDF | pypdf |
| OCR | pytesseract + Pillow |
| RSS/Podcast | feedparser |
| LLM (cloud) | OpenRouter / Anthropic API |
| LLM (local, planned) | Ollama serving the fine-tuned GGUF model |

---

## Database schema overview

The schema has two parallel tracks that have evolved alongside each other:

**Content track** (earlier, coarser):
- `Content` — a submitted URL/file with status (pending / ready / error)
- `ContentText` — stores `raw_transcript`, `corrected_transcript`, `ocr_text_corpus`, and `cleaned_text` separately so reconciliation steps are auditable
- `QuestionSet` → `Question` — LLM-generated question sets tied to a content item
- `QuizAttempt` → `Answer` — user attempts with per-answer scoring and LLM grading
- `ScheduleState` — step-indexed spaced-repetition state per content item

**Concept track** (later, finer-grained):
- `Concept` — a named concept extracted from content, with embedding and canonical name for deduplication/merging
- `ConceptEvidence` — links a concept to the specific `ContentSegment` that sourced it, with character offsets and confidence
- `ConceptMergeAudit` — records when similar concepts were merged, with similarity score and rationale
- `QuestionProbe` — a Bloom-level-tagged question tied to a concept (rather than raw content)
- `ConceptSchedule` — full SM-2 state per concept: `ease_factor`, `interval_days`, `lapses`, `repetitions`, `bloom_stage`
- `ReviewEvent` — immutable log of each review, capturing `self_comfort`, `is_correct`, and `score`

The `ConceptSchedule.bloom_stage` advances through the six Bloom levels as a concept is mastered, so the difficulty of probes escalates over time (recall → explain → apply → analyse → evaluate → create).

---

## Spaced-repetition algorithm

Modelled on SM-2 (the algorithm behind Anki). Key fields on `ConceptSchedule`:
- `ease_factor` — starts at 2.5, adjusts up/down based on review performance
- `interval_days` — current gap before next review; grows multiplicatively on success
- `lapses` — count of failed reviews; triggers interval reset
- `repetitions` — total successful reviews; gates interval growth
- `bloom_stage` — which Bloom level the next probe targets

On a successful review the interval is multiplied by `ease_factor`; on failure it resets to 1 day and `lapses` increments. `ease_factor` is clamped to a minimum so items don't become impossibly frequent.

---

## Content ingestion pipeline

1. User submits URL / file
2. Source-appropriate extractor runs:
   - **YouTube**: `yt-dlp` downloads audio; Whisper transcribes; `raw_transcript` stored; optional correction pass writes `corrected_transcript`
   - **PDF**: `pypdf` extracts text; OCR fallback via `pytesseract` / Pillow for scanned pages; both stored so reconciliation diffs are preserved
   - **Web page**: `trafilatura` / `readability-lxml` strip boilerplate; `BeautifulSoup4` used for edge cases
   - **RSS/Podcast**: `feedparser` (episode selection + audio download not yet implemented)
3. `clean_text()` normalises whitespace and paragraph boundaries
4. Cleaned text chunked into 200–600 word segments stored as `ContentSegment` rows
5. LLM generates `QuestionSet` for the content; concepts extracted and linked as `ConceptEvidence`

---

## LLM integration

`app/llm/` contains client wrappers for both cloud and (planned) local inference.

- **Cloud path**: OpenRouter, configured via `USE_LOCAL_LLM=false`. Used for question generation and answer grading.
- **Local path**: `USE_LOCAL_LLM=true` flag exists but the Ollama integration has not been wired end-to-end yet. The fine-tuned model lives in `finetune/merged_model/` and needs to be GGUF-quantised and registered with Ollama before this path works.

The question-generation prompt instructs the LLM to return a specific JSON schema (one question per Bloom level). The same prompt format was used to generate all fine-tuning training data, so the fine-tuned model is trained to reproduce exactly what the app expects.

---

## Fine-tuning pipeline

See [finetune/CLAUDE.md](finetune/CLAUDE.md) for full detail. Summary:

- **Goal**: replace cloud LLM calls with a local Qwen2.5-3B model served via Ollama
- **Current best model**: epoch 4, `max_seq_length=4096` — **69.2% JSON validity** overall, **76.0% on short prompts**
- **Base model baseline**: 45.4% JSON validity (untuned)
- **Target**: >95% — gap remains; likely requires more training data or a larger base model
- **Key lesson**: eval loss is not a reliable proxy for JSON validity on this task. Always measure output validity directly.

---

## Pending / incomplete work

- **Ollama integration**: `USE_LOCAL_LLM` flag is wired in config but not connected to actual local inference. Needs: GGUF export from `merged_model/`, Ollama model registration, and swap of the HTTP client in `app/llm/`.
- **RSS ingestion**: `app/ingest/rss.py` raises `NotImplementedError`. Episode selection and audio download need implementing.
- **Answer grading**: `grader_model` field exists on `QuizAttempt` but grading logic is not implemented — answers are stored unscored.
- **Concept extraction**: `ConceptEvidence` and `Concept` tables exist but the pipeline step that populates them from new content is not complete.
- **Frontend**: no UI exists yet; the FastAPI routes are stubs.

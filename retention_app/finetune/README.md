# Fine-Tuning Pipeline

QLoRA fine-tuning pipeline for `Qwen/Qwen3.5-4B` on the braintrashtogold question-generation task.
The fine-tuned model is exported to GGUF and served via Ollama as a drop-in replacement for the
OpenRouter API calls in the main app.

---

## Hardware requirements

- GPU: RTX 4070 Super (12 GB VRAM) or equivalent
- Python 3.11+

---

## Installation

```bash
pip install -r requirements.txt
```

Unsloth must be installed separately; follow the platform-specific instructions at
https://github.com/unslothai/unsloth#installation.

---

## Input files (user-supplied before running)

| File | Contents |
|---|---|
| `data/raw/wikipedia_topics.txt` | One Wikipedia article title per line |
| `data/raw/youtube_urls.txt` | One YouTube URL per line |
| `data/raw/pdfs/` | PDF files (arXiv papers or similar) |
| `data/raw/conversations/` | `.txt` files containing LLM conversation exports |

---

## Pipeline steps

Run the scripts in order from `finetune/`:

```bash
python scripts/01_collect_wikipedia.py
python scripts/02_collect_transcripts.py
python scripts/03_extract_pdfs.py
python scripts/04_clean_conversations.py
python scripts/05_chunk_sources.py
python scripts/06_generate_training_data.py    # requires ANTHROPIC_API_KEY env var
python scripts/07_validate_and_format.py
python scripts/08_train.py
python scripts/09_evaluate.py
```

Intermediate outputs are written to `data/` subdirectories so each step can be re-run
independently if needed.

---

## Enabling the local model in the app

After training, export and serve with Ollama:

```bash
# Inside 08_train.py output — or run manually after training:
ollama create braintrashtogold-qwen -f Modelfile
ollama serve
```

Then set in `retention_app/.env`:

```
USE_LOCAL_LLM=true
LOCAL_LLM_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=braintrashtogold-qwen
```

Restart the app — question generation will use the local model with no other changes.
Set `USE_LOCAL_LLM=false` to revert to OpenRouter at any time.

---

## Expected eval targets

| Metric | Target |
|---|---|
| JSON validity rate | >95% |
| Bloom level accuracy | Spot-check 30–50 examples manually |
| Inference speed | ~40–60 tokens/sec on RTX 4070 Super |

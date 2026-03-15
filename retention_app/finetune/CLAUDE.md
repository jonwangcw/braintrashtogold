# Fine-Tuning Pipeline — Working Context

QLoRA fine-tune of Qwen2.5-3B-Instruct to generate Bloom's Taxonomy quiz questions as structured JSON.
Current best model: epoch 4, seq_len=4096 → **69.2% JSON validity** (base model baseline: 45.4%).
Target: >95% JSON validity. Gap remains open.

---

## Environment & hardware

- **GPU**: RTX 4070 Super, 12 GB VRAM
- **Python**: `retention_app/.venv/Scripts/python` — always use the venv, not system python
- **PATH**: prefix commands with `export PATH="$PATH:/c/Program Files/CMake/bin"` for llama.cpp/GGUF operations
- **PYTHONIOENCODING=utf-8**: required for any script that prints non-ASCII — Windows console crashes otherwise
- **Shell**: bash on Windows 11 — use Unix path syntax (`/c/Users/...`)

---

## Common commands

```bash
export PATH="$PATH:/c/Program Files/CMake/bin"
cd c:/Users/jonwa/Rot2Gold/braintrashtogold/retention_app/finetune
PYTHON=/c/Users/jonwa/Rot2Gold/braintrashtogold/retention_app/.venv/Scripts/python

# Quick sanity check (30 examples, ~7 min):
PYTHONIOENCODING=utf-8 $PYTHON scripts/09_evaluate.py --max-eval 30

# Full eval (~50 min):
PYTHONIOENCODING=utf-8 $PYTHON scripts/09_evaluate.py

# Full eval with base model comparison (~90 min total):
PYTHONIOENCODING=utf-8 $PYTHON scripts/09_evaluate.py --base-model-also

# Export a specific checkpoint to merged_model/:
$PYTHON scripts/export_checkpoint.py --checkpoint checkpoints/checkpoint-NNN

# Train:
$PYTHON scripts/08_train.py
```

---

## Model state

| Checkpoint | Epoch | eval_loss | JSON validity |
|---|---|---|---|
| checkpoint-130 | 1 | 1.521 | — |
| checkpoint-260 | 2 | **1.500** (best loss) | 52.4% |
| checkpoint-390 | 3 | 1.522 | — |
| checkpoint-520 | 4 | 1.564 | **69.2%** (best validity) |

`merged_model/` currently holds **checkpoint-520 (epoch 4)**.

**Critical**: eval_loss is NOT a reliable proxy for JSON validity on this task. Epoch 4 has worse loss but substantially better output. Always measure JSON validity — don't stop at loss.

---

## Training gotchas

- **max_seq_length must cover p95+ of training data.** Data: mean=1702, p95=2502, max=8024 tokens. At 1024: 99.6% of examples truncated (model never saw a complete training example). At 2048: 16% truncated. Current setting 4096 covers 99.3%, with 7 examples filtered out entirely.
- **Filter, don't truncate.** Examples exceeding max_seq_length are dropped before training, not padded/truncated. Truncated sequences teach the model wrong stopping points — this is what caused the original missing-`}` failure mode.
- **Unsloth `save_pretrained_merged` does not overwrite stale safetensors.** `08_train.py` deletes old `.safetensors` files before saving — do not remove that cleanup code.
- **CUDA "unknown error" between GPU scripts** = VRAM not fully released. Re-run in a fresh process.

---

## Eval gotchas

- **Transformers 5.x**: `apply_chat_template(tokenize=True, return_tensors="pt")` returns `BatchEncoding`, not a tensor. Extract `.input_ids` before passing to model. Already handled in `09_evaluate.py`.
- **MAX_INPUT_LEN=1248**: prompt tokens are hard-capped at inference. ~17% of eval examples (31/185 with full_tokens >2048) have their prompts truncated at inference time. This puts a ceiling on eval scores independent of model quality.
- **`raw + "}"` fallback** in `09_evaluate.py` is intentional. The model occasionally stops one token early; this recovers those cases. Do not remove it.
- **30-sample checks can be misleading**: random sampling can land on easier examples. Previous 30-sample runs showed ~70% while full 185-example runs showed 59.5% (older model). Use full eval for any real decision.

---

## Data

- **Split**: 85/15 random. Train: 1,039 examples (7 dropped for exceeding 4096 tokens). Eval: 185 examples.
- **Source**: Claude Sonnet via `scripts/06_generate_training_data.py`, using the exact prompt format from `app/llm/prompts.py`.
- **Format**: ChatML conversations (`system`/`human`/`gpt` roles) stored as JSONL.
- **Eval output**: `data/eval_results.json` (aggregate) + `data/eval_results_detailed.json` (per-example with token lengths and short/long split at 2048 tokens).

---

## Pending work

- **App integration**: `USE_LOCAL_LLM` flag exists in `app/config.py` and `app/llm/openrouter_client.py` but the local model has not been wired to Ollama and tested end-to-end in the app.
- **GGUF export**: `merged_model.Q4_K_M.gguf` may be stale (from an earlier run). Re-export after finalising the model.
- **Short vs long analysis**: `09_evaluate.py` now reports validity for short (<=2048 tokens) vs long (>2048 tokens) examples separately. Compare these groups to determine whether the 31 long eval examples are disproportionately failing.

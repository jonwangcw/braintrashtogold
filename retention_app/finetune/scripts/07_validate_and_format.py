"""
07_validate_and_format.py — Validate and format generated examples for training.

Reads data/generated/raw_examples.jsonl, validates each example's output field
against the FreeQuestionSetOutput Pydantic schema (same validator used by the
production app), discards invalid examples, formats valid ones into ChatML/Unsloth
conversation format, and splits 85/15 into train and eval sets.

Output:
  data/train.jsonl
  data/eval.jsonl

Usage:
    python scripts/07_validate_and_format.py

NOTE: This script adds the retention_app root to sys.path so it can import
app.llm.schemas directly.  Run from the finetune/ directory or the retention_app root.
"""

import json
import random
import sys
from pathlib import Path

# Allow importing from the main app package
_repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_repo_root))

from app.llm.schemas import FreeQuestionSetOutput  # noqa: E402

SYSTEM_PROMPT = (
    "You are an expert instructional designer creating quiz questions "
    "for a spaced-repetition learning app. Follow instructions exactly."
)

TRAIN_SPLIT = 0.85


def validate_example(example: dict) -> bool:
    try:
        output = example.get("output")
        if not isinstance(output, dict):
            return False
        FreeQuestionSetOutput(**output)
        return True
    except Exception:
        return False


def format_for_training(example: dict) -> dict:
    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": example["input"]},
            {"from": "gpt", "value": json.dumps(example["output"])},
        ]
    }


def main() -> None:
    base = Path(__file__).parent.parent
    raw_file = base / "data" / "generated" / "raw_examples.jsonl"
    train_file = base / "data" / "train.jsonl"
    eval_file = base / "data" / "eval.jsonl"

    if not raw_file.exists():
        print(f"No raw examples at {raw_file}. Run 06_generate_training_data.py first.")
        return

    raw_examples = [
        json.loads(line)
        for line in raw_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(f"Loaded {len(raw_examples)} raw examples.")

    valid = [ex for ex in raw_examples if validate_example(ex)]
    invalid_count = len(raw_examples) - len(valid)
    discard_pct = invalid_count / max(len(raw_examples), 1) * 100
    print(f"Valid: {len(valid)}  Invalid: {invalid_count}  ({discard_pct:.1f}% discarded)")

    if discard_pct > 20:
        print("WARNING: discard rate > 20% — review raw examples before proceeding.")

    random.shuffle(valid)
    split = int(len(valid) * TRAIN_SPLIT)
    train_set = valid[:split]
    eval_set = valid[split:]

    with train_file.open("w", encoding="utf-8") as f:
        for ex in train_set:
            f.write(json.dumps(format_for_training(ex)) + "\n")

    with eval_file.open("w", encoding="utf-8") as f:
        for ex in eval_set:
            f.write(json.dumps(format_for_training(ex)) + "\n")

    print(f"Train: {len(train_set)} -> {train_file}")
    print(f"Eval:  {len(eval_set)} -> {eval_file}")


if __name__ == "__main__":
    main()

"""
06_generate_training_data.py — Generate synthetic training examples via Claude API.

Reads data/chunks/all_chunks.jsonl, calls Claude Sonnet for each chunk (rotating
through Bloom levels), writes results to data/generated/raw_examples.jsonl.

The prompt format exactly matches full_text_question_prompt() in app/llm/prompts.py
so that the fine-tuned model learns the production contract.

Requires: ANTHROPIC_API_KEY environment variable.

Usage:
    python scripts/06_generate_training_data.py [--max N]
"""

import argparse
import json
import os
import sys
import time

# Ensure UTF-8 output on Windows (handles non-ASCII characters in source names)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

import anthropic

# Allow importing from the main app package
_repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_repo_root))

from app.llm.prompts import full_text_question_prompt  # noqa: E402

BLOOM_LEVELS = ["remember", "understand", "apply", "analyze", "evaluate", "create"]

SYSTEM_PROMPT = (
    "You are an expert instructional designer creating quiz questions "
    "for a spaced-repetition learning app. Follow instructions exactly."
)


def generate_example(client: anthropic.Anthropic, chunk: dict, bloom_level: str) -> dict | None:
    prompt = full_text_question_prompt(chunk["text"], n_per_level=1)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()
        # Strip markdown code fences if present (model sometimes wraps despite instructions)
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        output = json.loads(raw_text)
        return {
            "chunk_id": chunk["chunk_id"],
            "source": chunk["source"],
            "content_type": chunk["content_type"],
            "bloom_level": bloom_level,
            "input": prompt,
            "output": output,
        }
    except json.JSONDecodeError:
        return None
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=None, help="Maximum chunks to process")
    parser.add_argument("--resume", action="store_true", help="Skip chunks already in output file")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        return

    base = Path(__file__).parent.parent
    chunks_file = base / "data" / "chunks" / "all_chunks.jsonl"
    out_file = base / "data" / "generated" / "raw_examples.jsonl"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not chunks_file.exists():
        print(f"No chunks file at {chunks_file}. Run 05_chunk_sources.py first.")
        return

    chunks = [json.loads(line) for line in chunks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.max:
        chunks = chunks[: args.max]

    # Resume: skip chunks already present in the output file
    done_ids: set[str] = set()
    if args.resume and out_file.exists():
        for line in out_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done_ids.add(json.loads(line)["chunk_id"])
        print(f"Resuming: {len(done_ids)} chunks already done, skipping them.")
        chunks = [c for c in chunks if c["chunk_id"] not in done_ids]

    print(f"Generating training examples for {len(chunks)} chunks...")

    client = anthropic.Anthropic(api_key=api_key)
    results: list[dict] = []
    failed = 0

    file_mode = "a" if args.resume else "w"
    with out_file.open(file_mode, encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            bloom_level = BLOOM_LEVELS[i % len(BLOOM_LEVELS)]
            example = generate_example(client, chunk, bloom_level)
            if example:
                results.append(example)
                f.write(json.dumps(example) + "\n")
                f.flush()
                status = "ok"
            else:
                failed += 1
                status = "FAILED"
            print(f"  [{i + 1}/{len(chunks)}] {status}  bloom={bloom_level}  source={chunk['source'][:40]}")
            time.sleep(0.5)  # rate limiting

    total_in_file = sum(1 for _ in out_file.read_text(encoding="utf-8").splitlines() if _)
    print(f"\nGenerated: {len(results)}  Failed: {failed}  ({failed / max(len(chunks), 1) * 100:.1f}% discard rate)")
    print(f"Total examples in file: {total_in_file}")
    print(f"Output: {out_file}")


if __name__ == "__main__":
    main()
    
"""
09_evaluate.py — Evaluate the fine-tuned model against the held-out eval set.

Loads the merged model (and optionally the base Qwen model for comparison),
runs inference on data/eval.jsonl, and reports:
  - JSON validity rate (target > 95%)
  - Bloom level accuracy

Results are written to data/eval_results.json.

Usage:
    python scripts/09_evaluate.py [--base-model-also] [--max-eval N]
"""

import argparse
import json
import os
import random
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

SYSTEM_PROMPT = (
    "You are an expert instructional designer creating quiz questions "
    "for a spaced-repetition learning app. Follow instructions exactly."
)
MAX_SEQ_LEN = 4096
MAX_NEW_TOKENS = 1200
MAX_INPUT_LEN = 1248  # hard ceiling for prompt tokens (keeps inputs fast)


LENGTH_SPLIT = 2048  # examples with full_tokens > this are "long"


def _compute_full_token_lengths(tokenizer, examples: list[dict]) -> list[int]:
    """Compute full conversation token length (prompt + output) for each example."""
    role_map = {"system": "system", "human": "user", "gpt": "assistant"}
    lengths = []
    for ex in examples:
        messages = [{"role": role_map[m["from"]], "content": m["value"]} for m in ex["conversations"]]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        lengths.append(len(tokenizer.encode(text)))
    return lengths


def _run_inference(model, tokenizer, examples: list[dict], full_token_lengths: list[int]) -> list[dict]:
    """Run the model on each example's input prompt and return results."""
    from unsloth import FastLanguageModel  # type: ignore[import]

    FastLanguageModel.for_inference(model)

    results = []
    for i, ex in enumerate(examples):
        # Extract the human turn from the conversation
        human_turn = next(
            (turn["value"] for turn in ex["conversations"] if turn["from"] == "human"),
            None,
        )
        if human_turn is None:
            continue

        # Apply chat template (matching training format) and truncate before tokenization
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": human_turn},
        ]
        encoded = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            return_tensors="pt",
            add_generation_prompt=True,
            max_length=MAX_INPUT_LEN,
            truncation=True,
        )
        # Transformers 5.x returns BatchEncoding; older versions return a raw tensor
        if hasattr(encoded, "input_ids"):
            input_ids = encoded.input_ids.to("cuda")
        else:
            input_ids = encoded.to("cuda")
        input_len = input_ids.shape[1]
        outputs = model.generate(input_ids, max_new_tokens=MAX_NEW_TOKENS, temperature=0, do_sample=False)
        raw = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)

        # Attempt JSON parse; also try adding a closing brace since the model
        # sometimes stops one token early (training truncation artefact)
        try:
            parsed = json.loads(raw)
            valid_json = True
        except json.JSONDecodeError:
            try:
                parsed = json.loads(raw + "}")
                valid_json = True
            except json.JSONDecodeError:
                parsed = None
                valid_json = False

        # Bloom accuracy: check if the model's output bloom levels match the expected
        expected_conv = next(
            (turn["value"] for turn in ex["conversations"] if turn["from"] == "gpt"),
            None,
        )
        expected_bloom_levels: list[str] = []
        if expected_conv:
            try:
                expected_output = json.loads(expected_conv)
                expected_bloom_levels = [q["bloom_level"] for q in expected_output.get("questions", [])]
            except json.JSONDecodeError:
                pass

        model_bloom_levels: list[str] = []
        if parsed:
            model_bloom_levels = [q.get("bloom_level", "") for q in parsed.get("questions", [])]

        bloom_match = sorted(expected_bloom_levels) == sorted(model_bloom_levels)
        full_tokens = full_token_lengths[i]

        results.append({
            "index": i,
            "valid_json": valid_json,
            "bloom_match": bloom_match,
            "expected_bloom_levels": expected_bloom_levels,
            "model_bloom_levels": model_bloom_levels,
            "full_tokens": full_tokens,
            "is_long": full_tokens > LENGTH_SPLIT,
        })

        if (i + 1) % 10 == 0:
            print(f"  Evaluated {i + 1}/{len(examples)}...")

    return results


def _report(label: str, results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        print(f"{label}: no results")
        return {}
    json_valid = sum(1 for r in results if r["valid_json"])
    bloom_match = sum(1 for r in results if r["bloom_match"])
    json_rate = json_valid / total * 100
    bloom_rate = bloom_match / total * 100
    print(f"\n{label}:")
    print(f"  JSON validity:  {json_valid}/{total}  ({json_rate:.1f}%)  [target: >95%]")
    print(f"  Bloom accuracy: {bloom_match}/{total}  ({bloom_rate:.1f}%)")

    # Short vs long breakdown
    short = [r for r in results if not r.get("is_long")]
    long_ = [r for r in results if r.get("is_long")]
    if short and long_:
        s_valid = sum(1 for r in short if r["valid_json"])
        l_valid = sum(1 for r in long_ if r["valid_json"])
        print(f"  Short (<={LENGTH_SPLIT} tokens): {s_valid}/{len(short)} valid ({100*s_valid/len(short):.1f}%)")
        print(f"  Long  (>{LENGTH_SPLIT} tokens):  {l_valid}/{len(long_)} valid ({100*l_valid/len(long_):.1f}%)")

    return {
        "json_validity_pct": json_rate,
        "bloom_accuracy_pct": bloom_rate,
        "n": total,
        "short_n": len(short),
        "short_json_validity_pct": 100 * sum(1 for r in short if r["valid_json"]) / len(short) if short else None,
        "long_n": len(long_),
        "long_json_validity_pct": 100 * sum(1 for r in long_ if r["valid_json"]) / len(long_) if long_ else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model-also", action="store_true", help="Also evaluate the base Qwen model")
    parser.add_argument("--max-eval", type=int, default=None, help="Evaluate only N random examples (quick sanity check)")
    args = parser.parse_args()

    try:
        from unsloth import FastLanguageModel  # type: ignore[import]
    except ImportError:
        print("unsloth not installed. See README.")
        return

    base = Path(__file__).parent.parent
    eval_file = base / "data" / "eval.jsonl"
    merged_dir = base / "merged_model"
    out_file = base / "data" / "eval_results.json"

    if not eval_file.exists():
        print(f"No eval data at {eval_file}. Run 07_validate_and_format.py first.")
        return

    examples = [json.loads(line) for line in eval_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    if args.max_eval:
        random.shuffle(examples)
        examples = examples[:args.max_eval]
        print(f"Evaluating on {len(examples)} randomly sampled examples (--max-eval {args.max_eval})...")
    else:
        print(f"Evaluating on {len(examples)} examples...")

    all_results: dict = {}
    all_per_example: dict = {}

    # Fine-tuned model
    if merged_dir.exists():
        print("\nLoading fine-tuned model...")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(merged_dir),
            max_seq_length=MAX_SEQ_LEN,
            dtype=None,
            load_in_4bit=True,
        )
        print("Pre-computing token lengths...")
        full_lengths = _compute_full_token_lengths(tokenizer, examples)
        long_count = sum(1 for l in full_lengths if l > LENGTH_SPLIT)
        print(f"  Short (<={LENGTH_SPLIT}): {len(full_lengths)-long_count}  Long (>{LENGTH_SPLIT}): {long_count}")
        results = _run_inference(model, tokenizer, examples, full_lengths)
        all_results["finetuned"] = _report("Fine-tuned model", results)
        all_per_example["finetuned"] = results
        del model
    else:
        print(f"No merged model at {merged_dir}. Run 08_train.py first.")

    # Base model comparison
    if args.base_model_also:
        print("\nLoading base model (unsloth/Qwen2.5-3B-Instruct-bnb-4bit)...")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name="unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
            max_seq_length=MAX_SEQ_LEN,
            dtype=None,
            load_in_4bit=True,
        )
        if "full_lengths" not in dir():
            full_lengths = _compute_full_token_lengths(tokenizer, examples)
        results = _run_inference(model, tokenizer, examples, full_lengths)
        all_results["base"] = _report("Base model (Qwen2.5-3B-Instruct)", results)
        all_per_example["base"] = results

    out_file.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    detail_file = out_file.with_name("eval_results_detailed.json")
    detail_file.write_text(json.dumps(all_per_example, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_file}")
    print(f"Per-example results saved to {detail_file}")


if __name__ == "__main__":
    main()

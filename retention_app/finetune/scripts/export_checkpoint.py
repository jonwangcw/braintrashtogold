"""
export_checkpoint.py — Merge a LoRA checkpoint into merged_model/.

Usage:
    python scripts/export_checkpoint.py --checkpoint checkpoints/checkpoint-262
"""

import argparse
import os
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True, help="Path to LoRA checkpoint dir")
    args = parser.parse_args()

    try:
        from unsloth import FastLanguageModel  # type: ignore[import]
    except ImportError:
        print("unsloth not installed.")
        return

    base = Path(__file__).parent.parent
    checkpoint_dir = Path(args.checkpoint)
    if not checkpoint_dir.is_absolute():
        checkpoint_dir = base / checkpoint_dir
    merged_dir = base / "merged_model"
    merged_dir.mkdir(exist_ok=True)

    print(f"Loading base model + adapter from {checkpoint_dir}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )

    print("Merging and saving to merged_model/...")
    for f in merged_dir.glob("*.safetensors"):
        f.unlink()
    (merged_dir / "model.safetensors.index.json").unlink(missing_ok=True)
    model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")
    print("Done.")


if __name__ == "__main__":
    main()

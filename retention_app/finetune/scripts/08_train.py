"""
08_train.py — QLoRA fine-tune Qwen/Qwen3.5-4B via Unsloth.

Reads data/train.jsonl and data/eval.jsonl, runs SFTTrainer with QLoRA adapters,
saves checkpoints to checkpoints/ and exports the merged model to merged_model/.
Also exports GGUF (q4_k_m) to gguf_model/ and writes a Modelfile for Ollama.

Requires unsloth to be installed (see README for installation instructions).
GPU with >= 12 GB VRAM recommended (tested on RTX 4070 Super).

Usage:
    python scripts/08_train.py
"""

import os
from pathlib import Path

# Reduce VRAM fragmentation
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
# Triton JIT compilation is broken on Windows — disable torch.compile
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")


def main() -> None:
    # Import here so the script is importable without unsloth installed (for linting)
    try:
        from unsloth import FastLanguageModel  # type: ignore[import]
        from trl import SFTTrainer  # type: ignore[import]
        from transformers import TrainingArguments  # type: ignore[import]
        from datasets import load_dataset  # type: ignore[import]
    except ImportError as exc:
        print(f"Import error: {exc}")
        print("Install unsloth: https://github.com/unslothai/unsloth#installation")
        return

    base = Path(__file__).parent.parent
    train_file = base / "data" / "train.jsonl"
    eval_file = base / "data" / "eval.jsonl"
    checkpoints_dir = base / "checkpoints"
    merged_dir = base / "merged_model"
    gguf_dir = base / "gguf_model"

    if not train_file.exists():
        print(f"No training data at {train_file}. Run 07_validate_and_format.py first.")
        return

    checkpoints_dir.mkdir(exist_ok=True)
    merged_dir.mkdir(exist_ok=True)
    gguf_dir.mkdir(exist_ok=True)

    MAX_SEQ_LEN = 4096  # covers 99.3% of training data with no truncation

    print("Loading model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
        max_seq_length=MAX_SEQ_LEN,
        dtype=None,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    dataset = load_dataset("json", data_files={"train": str(train_file), "eval": str(eval_file)})

    # Drop examples that exceed MAX_SEQ_LEN rather than truncating them.
    # Truncated training examples teach the model incorrect stopping points.
    def within_length(example):
        role_map = {"system": "system", "human": "user", "gpt": "assistant"}
        messages = [{"role": role_map[m["from"]], "content": m["value"]} for m in example["conversations"]]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        return len(tokenizer.encode(text)) <= MAX_SEQ_LEN

    before = {k: len(dataset[k]) for k in dataset}
    dataset = dataset.filter(within_length)
    after = {k: len(dataset[k]) for k in dataset}
    for split in before:
        dropped = before[split] - after[split]
        print(f"  {split}: {after[split]} examples kept, {dropped} dropped (exceeded {MAX_SEQ_LEN} tokens)")

    def formatting_func(example):
        role_map = {"system": "system", "human": "user", "gpt": "assistant"}
        convs = example["conversations"]
        # Single example: convs is a list of turn dicts
        # Batch example: convs is a list of conversations (list of lists)
        if convs and isinstance(convs[0], list):
            texts = []
            for conv in convs:
                messages = [{"role": role_map[m["from"]], "content": m["value"]} for m in conv]
                texts.append(tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False))
            return texts
        else:
            messages = [{"role": role_map[m["from"]], "content": m["value"]} for m in convs]
            return [tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)]

    training_args = TrainingArguments(
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        warmup_steps=50,
        num_train_epochs=4,
        learning_rate=2e-4,
        fp16=False,
        bf16=True,
        logging_steps=25,
        output_dir=str(checkpoints_dir),
        save_strategy="epoch",
        eval_strategy="epoch",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["eval"],
        max_seq_length=MAX_SEQ_LEN,
        formatting_func=formatting_func,
        args=training_args,
    )

    print("Training...")
    trainer.train()

    print("Saving merged model...")
    # Remove stale weight shards so Unsloth writes fresh ones (avoids config/weight mismatch)
    import shutil
    for f in merged_dir.glob("*.safetensors"):
        f.unlink()
    (merged_dir / "model.safetensors.index.json").unlink(missing_ok=True)
    model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")

    print("Exporting GGUF (q4_k_m)...")
    model.save_pretrained_gguf(str(gguf_dir), tokenizer, quantization_method="q4_k_m")

    # Write Modelfile for Ollama
    modelfile_path = gguf_dir / "Modelfile"
    gguf_files = list(gguf_dir.glob("*.gguf"))
    if gguf_files:
        modelfile_path.write_text(f"FROM ./{gguf_files[0].name}\n", encoding="utf-8")
        print(f"Modelfile written to {modelfile_path}")
        print("\nTo serve with Ollama:")
        print(f"  ollama create braintrashtogold-qwen -f {modelfile_path}")
        print("  ollama serve")
    else:
        print("WARNING: No GGUF file found after export — check Unsloth output.")

    print("Done.")


if __name__ == "__main__":
    main()

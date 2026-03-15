"""
04_clean_conversations.py — Clean LLM conversation export files.

Reads .txt files in data/raw/conversations/, strips role labels (Human:, Assistant:,
User:, Claude:, etc.), UI artifacts, and blank scaffolding lines, then writes a
cleaned version to the same directory with a _cleaned suffix.

NOTE: Content from LLM conversation exports carries higher hallucination risk than
other source types. The app surfaces a disclaimer for chunks sourced from this type.

Usage:
    python scripts/04_clean_conversations.py
"""

import re
from pathlib import Path


# Patterns that indicate non-content lines
_ROLE_PATTERN = re.compile(
    r"^\s*(human|user|assistant|claude|gpt|system|ai)\s*:\s*",
    re.IGNORECASE,
)
_UI_ARTIFACT_PATTERN = re.compile(
    r"^\s*(\[.*?\]|<.*?>|\*{1,3}.*?\*{1,3}|---+|===+|Copy code|Show less|Show more)\s*$",
    re.IGNORECASE,
)


def clean_conversation(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        # Strip role prefixes, keep the content after them
        line = _ROLE_PATTERN.sub("", line)
        # Drop pure UI artifact lines
        if _UI_ARTIFACT_PATTERN.match(line):
            continue
        cleaned.append(line.rstrip())

    # Collapse runs of 3+ blank lines to a single blank line
    result: list[str] = []
    blank_run = 0
    for line in cleaned:
        if line == "":
            blank_run += 1
            if blank_run <= 1:
                result.append(line)
        else:
            blank_run = 0
            result.append(line)

    return "\n".join(result).strip()


def main() -> None:
    base = Path(__file__).parent.parent
    conv_dir = base / "data" / "raw" / "conversations"

    if not conv_dir.exists() or not list(conv_dir.glob("*.txt")):
        print(f"No .txt files found in {conv_dir}. Place conversation exports there and re-run.")
        return

    for txt_file in sorted(conv_dir.glob("*.txt")):
        if txt_file.stem.endswith("_cleaned"):
            continue
        out_file = txt_file.with_stem(txt_file.stem + "_cleaned")
        if out_file.exists():
            print(f"  Already cleaned: {txt_file.name}")
            continue
        raw = txt_file.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_conversation(raw)
        out_file.write_text(cleaned, encoding="utf-8")
        print(f"  Cleaned: {txt_file.name} -> {out_file.name}")

    print("Done.")


if __name__ == "__main__":
    main()

"""
05_chunk_sources.py — Chunk all cleaned source texts into training-ready segments.

Reads from:
  data/raw/wikipedia_articles.json
  data/raw/transcripts/*.txt    (cleaned by 02_collect_transcripts.py)
  data/raw/pdfs/*.txt           (extracted by 03_extract_pdfs.py)
  data/raw/conversations/*_cleaned.txt   (cleaned by 04_clean_conversations.py)

Splits on paragraph boundaries, targets 200-600 words per chunk, discards chunks
< 100 words or pure boilerplate.

Writes data/chunks/all_chunks.jsonl with fields:
  chunk_id, source, content_type, text

Usage:
    python scripts/05_chunk_sources.py
"""

import json
import re
import uuid
from pathlib import Path


MIN_WORDS = 100
MAX_WORDS = 600
TARGET_WORDS = 400

_BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*(references|external links|see also|notes|bibliography|further reading)\s*$", re.IGNORECASE),
    re.compile(r"^\s*\[\d+\]\s*$"),  # lone citation markers
]


def _is_boilerplate(text: str) -> bool:
    return any(p.match(text.strip()) for p in _BOILERPLATE_PATTERNS)


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; fall back to single lines for transcripts."""
    if "\n\n" in text:
        return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    # No blank lines (e.g. VTT transcripts) — split on single newlines
    return [line.strip() for line in text.splitlines() if line.strip()]


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_text(text: str, source: str, content_type: str) -> list[dict]:
    paragraphs = _split_paragraphs(text)
    chunks: list[dict] = []
    current_parts: list[str] = []
    current_words = 0

    def flush() -> None:
        nonlocal current_parts, current_words
        if current_parts:
            combined = "\n\n".join(current_parts)
            wc = _word_count(combined)
            if wc >= MIN_WORDS and not _is_boilerplate(combined):
                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "source": source,
                    "content_type": content_type,
                    "text": combined,
                })
        current_parts = []
        current_words = 0

    for para in paragraphs:
        if _is_boilerplate(para):
            flush()
            continue
        wc = _word_count(para)
        if current_words + wc > MAX_WORDS and current_parts:
            flush()
        current_parts.append(para)
        current_words += wc
        if current_words >= TARGET_WORDS:
            flush()

    flush()
    return chunks


def main() -> None:
    base = Path(__file__).parent.parent
    out_file = base / "data" / "chunks" / "all_chunks.jsonl"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict] = []

    # Wikipedia
    wiki_file = base / "data" / "raw" / "wikipedia_articles.json"
    if wiki_file.exists():
        articles = json.loads(wiki_file.read_text(encoding="utf-8"))
        for article in articles:
            chunks = chunk_text(article["text"], source=article["title"], content_type="wikipedia")
            all_chunks.extend(chunks)
        print(f"Wikipedia: {len(articles)} articles -> {sum(1 for c in all_chunks if c['content_type'] == 'wikipedia')} chunks")

    # Transcripts
    transcript_dir = base / "data" / "raw" / "transcripts"
    for txt_file in sorted(transcript_dir.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text, source=txt_file.stem, content_type="youtube_transcript")
        all_chunks.extend(chunks)
    print(f"Transcripts: {sum(1 for c in all_chunks if c['content_type'] == 'youtube_transcript')} chunks")

    # PDFs
    pdf_dir = base / "data" / "raw" / "pdfs"
    for txt_file in sorted(pdf_dir.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text, source=txt_file.stem, content_type="paper")
        all_chunks.extend(chunks)
    print(f"PDFs: {sum(1 for c in all_chunks if c['content_type'] == 'paper')} chunks")

    # Conversations
    conv_dir = base / "data" / "raw" / "conversations"
    for txt_file in sorted(conv_dir.glob("*_cleaned.txt")):
        text = txt_file.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text, source=txt_file.stem, content_type="conversation")
        all_chunks.extend(chunks)
    print(f"Conversations: {sum(1 for c in all_chunks if c['content_type'] == 'conversation')} chunks")

    with out_file.open("w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk) + "\n")

    print(f"\nTotal chunks: {len(all_chunks)} -> {out_file}")


if __name__ == "__main__":
    main()

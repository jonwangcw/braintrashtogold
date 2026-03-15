"""
02_collect_transcripts.py — Download YouTube transcripts and clean them.

Reads data/raw/youtube_urls.txt (one URL per line), calls yt-dlp to download
auto-generated subtitles as VTT, then strips timestamps and collapses the output
to plain text paragraphs.  Cleaned transcripts are written as .txt files alongside
the raw VTT files in data/raw/transcripts/.

Usage:
    python scripts/02_collect_transcripts.py
"""

import html
import re
import sys

# Ensure UTF-8 output on Windows (handles non-ASCII characters in video titles)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import subprocess
import sys
from pathlib import Path


def _clean_vtt(vtt_text: str) -> str:
    """Strip VTT formatting and collapse to readable paragraphs."""
    lines = vtt_text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        # Decode HTML entities before any other processing
        line = html.unescape(line)
        # Skip header, metadata, cue timestamps, NOTE lines, and empty lines
        if line.startswith("WEBVTT"):
            continue
        if re.match(r"^(Kind|Language):", line):
            continue
        if re.match(r"^\d{2}:\d{2}", line):
            continue
        if re.match(r"^NOTE", line):
            continue
        # Strip inline VTT tags: <00:00:00.000>, <c>, </c>, etc.
        line = re.sub(r"<[^>]+>", "", line)
        line = line.strip()
        if line:
            cleaned.append(line)

    # Deduplicate consecutive identical lines (common in auto-generated subs)
    deduped: list[str] = []
    prev = ""
    for line in cleaned:
        if line != prev:
            deduped.append(line)
        prev = line

    return "\n".join(deduped)


def main() -> None:
    base = Path(__file__).parent.parent
    urls_file = base / "data" / "raw" / "youtube_urls.txt"
    out_dir = base / "data" / "raw" / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not urls_file.exists():
        print(f"No URLs file found at {urls_file}. Create it with one YouTube URL per line.")
        return

    urls = [
        line.strip()
        for line in urls_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    print(f"Processing {len(urls)} URLs...")

    for url in urls:
        print(f"  Downloading: {url}")
        result = subprocess.run(
            [
                sys.executable, "-m", "yt_dlp",
                "--write-auto-sub",
                "--skip-download",
                "--sub-format", "vtt",
                "--sub-lang", "en",
                "-o", str(out_dir / "%(title)s"),
                url,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  WARNING: yt-dlp failed for {url}\n  {result.stderr[:200]}")
            continue

    # Clean all VTT files that don't yet have a .txt counterpart
    for vtt_file in out_dir.glob("*.vtt"):
        txt_file = vtt_file.with_suffix(".txt")
        if txt_file.exists():
            continue
        cleaned = _clean_vtt(vtt_file.read_text(encoding="utf-8", errors="ignore"))
        txt_file.write_text(cleaned, encoding="utf-8")
        print(f"  Cleaned: {txt_file.name}")

    print("Done.")


if __name__ == "__main__":
    main()

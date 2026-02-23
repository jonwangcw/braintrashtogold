from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OCRSnippet:
    timestamp_seconds: float
    text: str
    confidence: float
    frame_path: str


def _timestamp_from_frame_name(frame_path: str, default_step_seconds: int = 15) -> float:
    stem = Path(frame_path).stem
    match = re.search(r"(\d+)$", stem)
    if not match:
        return 0.0
    # Frame names are 1-indexed when emitted by ffmpeg pattern (frame_000001.jpg).
    frame_number = int(match.group(1))
    return float(max(frame_number - 1, 0) * default_step_seconds)


def _ocr_single_frame(frame_path: str) -> OCRSnippet | None:
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return None

    with Image.open(frame_path) as image:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    words: list[str] = []
    confidences: list[float] = []
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        candidate = (text or "").strip()
        if not candidate:
            continue
        try:
            confidence_value = float(conf)
        except (TypeError, ValueError):
            continue
        if confidence_value < 0:
            continue
        words.append(candidate)
        confidences.append(confidence_value / 100.0)

    if not words:
        return None

    return OCRSnippet(
        timestamp_seconds=_timestamp_from_frame_name(frame_path),
        text=" ".join(words),
        confidence=sum(confidences) / len(confidences),
        frame_path=frame_path,
    )


def ocr_frames(frame_paths: list[str]) -> list[OCRSnippet]:
    snippets: list[OCRSnippet] = []
    for frame_path in frame_paths:
        snippet = _ocr_single_frame(frame_path)
        if snippet is not None:
            snippets.append(snippet)
    return snippets

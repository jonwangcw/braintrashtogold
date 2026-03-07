from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import shutil

import pytesseract
from PIL import Image, ImageOps, ImageStat

# If tesseract isn't on PATH, fall back to the standard Windows install location.
if shutil.which("tesseract") is None:
    _windows_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if _windows_default.exists():
        pytesseract.pytesseract.tesseract_cmd = str(_windows_default)


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


def _preprocess_for_ocr(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    stat = ImageStat.Stat(gray)
    if stat.mean[0] < 128:  # predominantly dark → invert so text is dark-on-white
        gray = ImageOps.invert(gray)
    return gray


def _ocr_single_frame(frame_path: str) -> OCRSnippet | None:
    try:
        with Image.open(frame_path) as image:
            preprocessed = _preprocess_for_ocr(image)
            data = pytesseract.image_to_data(
                preprocessed,
                output_type=pytesseract.Output.DICT,
                config="--psm 3",
            )
    except pytesseract.TesseractNotFoundError:
        raise  # surface missing binary immediately — do not hide
    except Exception:
        return None  # skip unreadable or corrupt frames

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

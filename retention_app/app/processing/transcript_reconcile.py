from __future__ import annotations

import re
from dataclasses import dataclass

from app.processing.ocr import OCRSnippet


@dataclass
class TranscriptCorrection:
    original: str
    corrected: str
    confidence: float
    evidence: list[str]


@dataclass
class ReconciledTranscript:
    corrected_transcript: str
    corrections: list[TranscriptCorrection]


def _tokenize_terms(text: str) -> list[str]:
    return re.findall(r"\b[A-Za-z][A-Za-z0-9\-]{2,}\b", text)


def _normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def reconcile_transcript_with_ocr(
    transcript: str,
    ocr_snippets: list[OCRSnippet],
    min_ocr_confidence: float = 0.55,
) -> ReconciledTranscript:
    if not ocr_snippets:
        return ReconciledTranscript(corrected_transcript=transcript, corrections=[])

    transcript_terms = _tokenize_terms(transcript)
    normalized_transcript_terms = {_normalized(term) for term in transcript_terms}

    ocr_term_occurrences: dict[str, list[OCRSnippet]] = {}
    for snippet in ocr_snippets:
        if snippet.confidence < min_ocr_confidence:
            continue
        for term in _tokenize_terms(snippet.text):
            if len(term) < 4:
                continue
            key = _normalized(term)
            if not key:
                continue
            ocr_term_occurrences.setdefault(key, []).append(snippet)

    corrected = transcript
    corrections: list[TranscriptCorrection] = []

    for ocr_key, occurrences in ocr_term_occurrences.items():
        if len(occurrences) < 2:
            continue
        if ocr_key in normalized_transcript_terms:
            continue

        candidate = max(
            (_tokenize_terms(occ.text) for occ in occurrences),
            key=lambda terms: sum(1 for term in terms if _normalized(term) == ocr_key),
            default=[],
        )
        replacement = next((term for term in candidate if _normalized(term) == ocr_key), "")
        if not replacement:
            continue

        best_match = None
        best_overlap = 0.0
        for term in transcript_terms:
            overlap = _prefix_overlap(_normalized(term), ocr_key)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = term

        if not best_match or best_overlap < 0.7:
            continue

        confidence = min(0.99, (sum(o.confidence for o in occurrences) / len(occurrences)) * best_overlap)
        corrected = re.sub(rf"\b{re.escape(best_match)}\b", replacement, corrected)
        corrections.append(
            TranscriptCorrection(
                original=best_match,
                corrected=replacement,
                confidence=round(confidence, 3),
                evidence=[o.text[:220] for o in occurrences[:3]],
            )
        )

    return ReconciledTranscript(corrected_transcript=corrected, corrections=corrections)


def _prefix_overlap(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    shared = 0
    for idx, ch in enumerate(left):
        if idx >= len(right) or right[idx] != ch:
            break
        shared += 1
    return shared / max(len(left), len(right))

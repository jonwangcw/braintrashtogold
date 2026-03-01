from dataclasses import dataclass

from app.ingest.common import detect_source_type, validate_url
from app.ingest.pdf import extract_text_from_pdf
from app.ingest.web import extract_webpage_text
from app.ingest.youtube import ingest_youtube
from app.processing.clean_text import clean_text


@dataclass
class IngestedContentPayload:
    cleaned_text: str
    source_type: str
    raw_transcript: str | None = None
    corrected_transcript: str | None = None
    ocr_text_corpus: str | None = None
    correction_annotations: str | None = None


async def ingest_source(source_type: str | None, source: str, artifacts_dir: str | None = None) -> IngestedContentPayload:
    if source_type is None:
        validate_url(source)
        resolved_source_type = detect_source_type(source)
    else:
        resolved_source_type = source_type

    if resolved_source_type == "youtube":
        result = await ingest_youtube(source, artifacts_dir=artifacts_dir)
        cleaned_text = clean_text(result.corrected_transcript)
        correction_annotations = "\n".join(
            f"{c.original} -> {c.corrected} (confidence={c.confidence})"
            for c in result.reconciliation.corrections
        )
        ocr_corpus = "\n".join(
            f"[{int(snippet.timestamp_seconds)}s|{snippet.confidence:.2f}] {snippet.text}"
            for snippet in result.ocr_snippets
        )
        return IngestedContentPayload(
            cleaned_text=cleaned_text,
            source_type=resolved_source_type,
            raw_transcript=result.raw_transcript,
            corrected_transcript=result.corrected_transcript,
            ocr_text_corpus=ocr_corpus,
            correction_annotations=correction_annotations,
        )

    if resolved_source_type == "webpage":
        raw_text = extract_webpage_text(source)
    elif resolved_source_type == "pdf":
        raw_text = extract_text_from_pdf(source)
    else:
        raise ValueError(f"Unsupported source type: {resolved_source_type}")

    return IngestedContentPayload(cleaned_text=clean_text(raw_text), source_type=resolved_source_type)

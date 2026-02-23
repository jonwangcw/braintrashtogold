from dataclasses import dataclass

from app.ingest.common import is_youtube_url, validate_url
from app.ingest.pdf import extract_text_from_pdf
from app.ingest.web import extract_webpage_text
from app.ingest.youtube import ingest_youtube
from app.processing.clean_text import clean_text


@dataclass
class IngestedContentPayload:
    cleaned_text: str
    raw_transcript: str | None = None
    corrected_transcript: str | None = None
    ocr_text_corpus: str | None = None
    correction_annotations: str | None = None


async def ingest_source(source_type: str, url: str, artifacts_dir: str | None = None) -> IngestedContentPayload:
    validate_url(url)
    if source_type == "youtube":
        result = await ingest_youtube(url, artifacts_dir=artifacts_dir)
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
            raw_transcript=result.raw_transcript,
            corrected_transcript=result.corrected_transcript,
            ocr_text_corpus=ocr_corpus,
            correction_annotations=correction_annotations,
        )
    elif source_type == "webpage":
        if is_youtube_url(url):
            raise ValueError("YouTube URLs must use source type youtube")
        raw_text = extract_webpage_text(url)
    elif source_type == "pdf":
        raw_text = extract_text_from_pdf(url)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")
    return IngestedContentPayload(cleaned_text=clean_text(raw_text))

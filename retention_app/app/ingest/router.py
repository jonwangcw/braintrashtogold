from app.ingest.common import validate_url
from app.ingest.pdf import extract_text_from_pdf
from app.ingest.web import extract_webpage_text
from app.ingest.youtube import ingest_youtube
from app.processing.clean_text import clean_text


async def ingest_source(source_type: str, url: str) -> str:
    validate_url(url)
    if source_type == "youtube":
        raw_text = await ingest_youtube(url)
    elif source_type == "webpage":
        raw_text = extract_webpage_text(url)
    elif source_type == "pdf":
        raw_text = extract_text_from_pdf(url)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")
    return clean_text(raw_text)

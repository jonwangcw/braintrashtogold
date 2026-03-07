from pypdf import PdfReader


def extract_pdf_title(path: str) -> str | None:
    reader = PdfReader(path)
    meta = reader.metadata
    if not meta:
        return None
    title = (meta.get("/Title") or "").strip() or None
    author = (meta.get("/Author") or "").strip() or None
    if not title:
        return None
    if not author:
        return title
    # Author field may use "and", ";", or "," as separators
    parts = [p.strip() for p in author.replace(" and ", ";").split(";") if p.strip()]
    if len(parts) >= 2:
        return f"{title} - {parts[0]} et al."
    return f"{title} - {parts[0]}" if parts else title


def is_text_based_pdf(path: str, page_limit: int = 3, min_chars: int = 50) -> bool:
    reader = PdfReader(path)
    sample_text = ""
    for page in reader.pages[:page_limit]:
        sample_text += page.extract_text() or ""
    return len(sample_text.strip()) >= min_chars


def extract_text_from_pdf(path: str) -> str:
    if not is_text_based_pdf(path):
        raise ValueError("invalid media (scanned PDF not supported)")
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

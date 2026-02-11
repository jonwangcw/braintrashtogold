from pypdf import PdfReader


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

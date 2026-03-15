"""
03_extract_pdfs.py — Extract plain text from PDF files.

Reads all .pdf files in data/raw/pdfs/ and writes a .txt file alongside each one
containing the extracted text.  Uses pypdf (already a dependency of the main app).

Usage:
    python scripts/03_extract_pdfs.py
"""

from pathlib import Path

import pypdf


def extract_pdf(pdf_path: Path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text.strip())
    return "\n\n".join(p for p in pages if p)


def main() -> None:
    base = Path(__file__).parent.parent
    pdf_dir = base / "data" / "raw" / "pdfs"

    if not pdf_dir.exists() or not list(pdf_dir.glob("*.pdf")):
        print(f"No PDF files found in {pdf_dir}. Place PDF files there and re-run.")
        return

    for pdf_file in sorted(pdf_dir.glob("*.pdf")):
        txt_file = pdf_file.with_suffix(".txt")
        if txt_file.exists():
            print(f"  Already extracted: {pdf_file.name}")
            continue
        try:
            text = extract_pdf(pdf_file)
            txt_file.write_text(text, encoding="utf-8")
            print(f"  Extracted: {pdf_file.name} ({len(text)} chars)")
        except Exception as exc:
            print(f"  ERROR extracting {pdf_file.name}: {exc}")

    print("Done.")


if __name__ == "__main__":
    main()

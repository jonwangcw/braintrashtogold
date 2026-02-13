import pytest

pytest.importorskip("pypdf")

from app.ingest import pdf as pdf_module


def test_scanned_pdf_rejected(monkeypatch):
    class FakePage:
        def extract_text(self):
            return ""

    class FakeReader:
        pages = [FakePage(), FakePage()]

    monkeypatch.setattr(pdf_module, "PdfReader", lambda _: FakeReader())
    with pytest.raises(ValueError, match="scanned PDF"):
        pdf_module.extract_text_from_pdf("fake.pdf")


def test_text_pdf_allowed(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "Some extracted text from pdf."

    class FakeReader:
        pages = [FakePage(), FakePage()]

    monkeypatch.setattr(pdf_module, "PdfReader", lambda _: FakeReader())
    text = pdf_module.extract_text_from_pdf("fake.pdf")
    assert "Some extracted text" in text

import pytest

from app.llm.question_gen import _validate_source_offsets
from app.llm.schemas import SourceSnippet


def test_validate_source_offsets_passes_with_chunk_aligned_span():
    cleaned_text = "a" * 2100
    source = SourceSnippet(evidence_id="ev1", quote="a" * 50, start_char=2000, end_char=2050)
    _validate_source_offsets([source], cleaned_text)


def test_validate_source_offsets_rejects_quote_mismatch():
    cleaned_text = "hello world"
    source = SourceSnippet(evidence_id="ev1", quote="nope", start_char=0, end_char=5)
    with pytest.raises(ValueError, match="quote mismatch"):
        _validate_source_offsets([source], cleaned_text)

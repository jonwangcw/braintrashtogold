import pytest

pytest.importorskip("pydantic")

from app.llm.schemas import QuestionSetOutput


def _question(i: int, bloom: str) -> dict:
    return {
        "question_id": f"q{i}",
        "bloom_level": bloom,
        "concept_id": "c1",
        "prompt": f"Prompt {i}",
        "expected_answer": "Answer",
        "key_points": ["point"],
        "required_evidence_refs": ["ev1"],
        "sources": [{"evidence_id": "ev1", "quote": "text", "start_char": 0, "end_char": 4}],
    }


def test_question_schema_enforces_counts():
    payload = {
        "content_id": "1",
        "questions": [_question(i, "remember" if i < 5 else "understand") for i in range(10)],
    }
    result = QuestionSetOutput.model_validate(payload)
    assert len(result.questions) == 10


def test_question_schema_rejects_wrong_split():
    payload = {
        "content_id": "1",
        "questions": [_question(i, "remember") for i in range(10)],
    }
    with pytest.raises(ValueError, match="5 remember and 5 understand"):
        QuestionSetOutput.model_validate(payload)

import pytest

pytest.importorskip("pydantic")

from app.llm.schemas import FreeQuestionSetOutput


def _free_question(bloom: str) -> dict:
    return {"bloom_level": bloom, "prompt": "Q", "expected_answer": "A", "key_points": ["p"]}


def test_free_question_schema_accepts_any_count():
    payload = {"questions": [_free_question("remember") for _ in range(5)]}
    result = FreeQuestionSetOutput.model_validate(payload)
    assert len(result.questions) == 5


def test_free_question_schema_accepts_all_bloom_levels():
    levels = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
    payload = {"questions": [_free_question(bl) for bl in levels]}
    result = FreeQuestionSetOutput.model_validate(payload)
    assert len(result.questions) == 6


def test_free_question_schema_rejects_empty():
    with pytest.raises(ValueError):
        FreeQuestionSetOutput.model_validate({"questions": []})

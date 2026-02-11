import pytest

pytest.importorskip("pydantic")

from app.llm.schemas import GradingOutput


def test_grading_schema_valid():
    payload = {
        "quiz_attempt_id": "1",
        "results": [
            {"question_id": "q1", "score": 1, "feedback": "Great"},
            {"question_id": "q2", "score": 0.5, "feedback": "Partial"},
        ],
    }
    result = GradingOutput.model_validate(payload)
    assert len(result.results) == 2


def test_grading_schema_rejects_score():
    payload = {
        "quiz_attempt_id": "1",
        "results": [{"question_id": "q1", "score": 0.7, "feedback": "Nope"}],
    }
    with pytest.raises(ValueError):
        GradingOutput.model_validate(payload)

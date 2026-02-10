import pytest

pytest.importorskip("pydantic")

from app.llm.schemas import QuestionSetOutput


def test_question_schema_enforces_counts():
    payload = {
        "content_id": "1",
        "questions": [
            {
                "question_id": f"q{i}",
                "question_type": "recall" if i < 5 else "explain",
                "prompt": f"Prompt {i}",
                "expected_answer": "Answer",
                "key_points": ["point"],
                "sources": [{"quote": "text", "start_char": 0, "end_char": 4}],
            }
            for i in range(10)
        ],
    }
    result = QuestionSetOutput.model_validate(payload)
    assert len(result.questions) == 10


def test_question_schema_rejects_wrong_split():
    payload = {
        "content_id": "1",
        "questions": [
            {
                "question_id": f"q{i}",
                "question_type": "recall",
                "prompt": f"Prompt {i}",
                "expected_answer": "Answer",
                "key_points": ["point"],
                "sources": [{"quote": "text", "start_char": 0, "end_char": 4}],
            }
            for i in range(10)
        ],
    }
    with pytest.raises(ValueError, match="5 recall and 5 explain"):
        QuestionSetOutput.model_validate(payload)

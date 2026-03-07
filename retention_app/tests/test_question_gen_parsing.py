import asyncio
import json

import pytest

pytest.importorskip("pydantic")

from app.llm import question_gen


class SequenceClient:
    def __init__(self, responses: list[str]):
        self._responses = iter(responses)

    async def complete(self, prompt: str) -> str:
        return next(self._responses)


def test_question_gen_rejects_empty_response(monkeypatch):
    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: SequenceClient(["   "]))

    with pytest.raises(ValueError, match="empty response"):
        asyncio.run(question_gen.generate_questions("text", "1"))


def test_question_gen_rejects_non_json(monkeypatch):
    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: SequenceClient(["not json"]))

    with pytest.raises(ValueError, match="non-JSON output"):
        asyncio.run(question_gen.generate_questions("text", "1"))


def test_question_gen_accepts_full_text_response(monkeypatch):
    questions = [
        {"bloom_level": bl, "prompt": f"Q {bl}", "expected_answer": "A", "key_points": ["p"]}
        for bl in ["remember", "understand", "apply", "analyze", "evaluate", "create"]
    ]
    response = json.dumps({"questions": questions})
    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: SequenceClient([response]))

    result = asyncio.run(question_gen.generate_questions("sample text", "content-1"))
    assert len(result.questions) == 6
    bloom_levels = {q.bloom_level.value for q in result.questions}
    assert bloom_levels == {"remember", "understand", "apply", "analyze", "evaluate", "create"}


def test_question_gen_accepts_fenced_json(monkeypatch):
    questions = [
        {"bloom_level": "remember", "prompt": "Q", "expected_answer": "A", "key_points": ["p"]}
    ]
    response = f"```json\n{json.dumps({'questions': questions})}\n```"
    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: SequenceClient([response]))

    result = asyncio.run(question_gen.generate_questions("text", "content-1"))
    assert len(result.questions) == 1

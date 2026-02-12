import asyncio

import pytest

pytest.importorskip("pydantic")

from app.llm import question_gen


def test_question_gen_rejects_empty_response(monkeypatch):
    class FakeClient:
        async def complete(self, prompt: str) -> str:
            return "   "

    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: FakeClient())

    with pytest.raises(ValueError, match="empty response"):
        asyncio.run(question_gen.generate_questions("text", "1"))


def test_question_gen_rejects_non_json(monkeypatch):
    class FakeClient:
        async def complete(self, prompt: str) -> str:
            return "not json"

    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: FakeClient())

    with pytest.raises(ValueError, match="non-JSON output"):
        asyncio.run(question_gen.generate_questions("text", "1"))

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


def test_question_gen_accepts_fenced_json(monkeypatch):
    class FakeClient:
        async def complete(self, prompt: str) -> str:
            return """```json
{
  \"content_id\": \"placeholder\",
  \"questions\": [
    {\"question_id\": \"q1\", \"question_type\": \"recall\", \"prompt\": \"p1\", \"expected_answer\": \"a1\", \"key_points\": [\"k1\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q2\", \"question_type\": \"recall\", \"prompt\": \"p2\", \"expected_answer\": \"a2\", \"key_points\": [\"k2\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q3\", \"question_type\": \"recall\", \"prompt\": \"p3\", \"expected_answer\": \"a3\", \"key_points\": [\"k3\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q4\", \"question_type\": \"recall\", \"prompt\": \"p4\", \"expected_answer\": \"a4\", \"key_points\": [\"k4\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q5\", \"question_type\": \"recall\", \"prompt\": \"p5\", \"expected_answer\": \"a5\", \"key_points\": [\"k5\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q6\", \"question_type\": \"explain\", \"prompt\": \"p6\", \"expected_answer\": \"a6\", \"key_points\": [\"k6\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q7\", \"question_type\": \"explain\", \"prompt\": \"p7\", \"expected_answer\": \"a7\", \"key_points\": [\"k7\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q8\", \"question_type\": \"explain\", \"prompt\": \"p8\", \"expected_answer\": \"a8\", \"key_points\": [\"k8\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q9\", \"question_type\": \"explain\", \"prompt\": \"p9\", \"expected_answer\": \"a9\", \"key_points\": [\"k9\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]},
    {\"question_id\": \"q10\", \"question_type\": \"explain\", \"prompt\": \"p10\", \"expected_answer\": \"a10\", \"key_points\": [\"k10\"], \"sources\": [{\"quote\": \"q\", \"start_char\": 0, \"end_char\": 1}]}
  ]
}
```"""

    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: FakeClient())

    result = asyncio.run(question_gen.generate_questions("text", "content-123"))
    assert result.content_id == "content-123"
    assert len(result.questions) == 10

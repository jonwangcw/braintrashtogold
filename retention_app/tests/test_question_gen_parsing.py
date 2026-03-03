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
        asyncio.run(question_gen.extract_concepts("text", "1"))


def test_question_gen_rejects_non_json(monkeypatch):
    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: SequenceClient(["not json"]))

    with pytest.raises(ValueError, match="non-JSON output"):
        asyncio.run(question_gen.extract_concepts("text", "1"))


def test_question_gen_accepts_fenced_json(monkeypatch):
    extraction = {
        "content_id": "placeholder",
        "concepts": [
            {
                "concept_id": "c1",
                "concept_name": "Retention",
                "summary": "Memory reinforcement",
                "evidence": [
                    {
                        "evidence_id": "ev1",
                        "quote": "text",
                        "start_char": 0,
                        "end_char": 4,
                        "chunk_index": 0,
                    }
                ],
            }
        ],
    }
    merge = {"actions": []}
    probe = {
        "question_id": "temp",
        "concept_id": "c1",
        "bloom_level": "remember",
        "prompt": "What is retention?",
        "expected_answer": "Retaining core ideas over time.",
        "key_points": ["spaced review"],
        "required_evidence_refs": ["ev1"],
        "sources": [{"evidence_id": "ev1", "quote": "text", "start_char": 0, "end_char": 4}],
    }

    responses = [
        f"```json\n{json.dumps(extraction)}\n```",
        f"```json\n{json.dumps(merge)}\n```",
        *[json.dumps(probe) for _ in range(10)],
    ]

    client = SequenceClient(responses)
    monkeypatch.setattr(question_gen, "OpenRouterClient", lambda: client)

    result = asyncio.run(question_gen.generate_questions("text", "content-123"))
    assert result.content_id == "content-123"
    assert len(result.questions) == 10

import json
import re

from app.config import settings
from app.llm.openrouter_client import OpenRouterClient
from app.llm.prompts import FULLTEXT_QUESTION_PROMPT_VERSION, full_text_question_prompt
from app.llm.schemas import FreeQuestionSetOutput

_JSON_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json_payload(raw_response: str) -> dict:
    stripped = raw_response.strip()
    if not stripped:
        raise ValueError("Question generation returned empty response from LLM")

    candidates: list[str] = [stripped]
    fenced = _JSON_CODE_BLOCK_RE.findall(stripped)
    candidates.extend(block.strip() for block in fenced if block.strip())

    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(stripped[first_brace : last_brace + 1])

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    preview = stripped[:500]
    raise ValueError(
        "Question generation returned non-JSON output. "
        f"Response preview: {preview}"
    )


async def generate_questions(
    cleaned_text: str,
    content_id: str,
    correction_hints: str | None = None,
    debug_logger=None,
) -> FreeQuestionSetOutput:
    client = OpenRouterClient()
    n_per_level = settings.questions_per_bloom_level
    prompt = full_text_question_prompt(cleaned_text, n_per_level, correction_hints)
    if debug_logger:
        debug_logger.section("QUESTION GENERATION PROMPT", prompt)
    response = await client.complete(prompt)
    if debug_logger:
        debug_logger.section("QUESTION GENERATION RESPONSE (raw)", response)
    if not response.strip():
        raise ValueError("Question generation returned empty response from LLM")
    payload = _extract_json_payload(response)
    question_set = FreeQuestionSetOutput.model_validate(payload)
    if debug_logger:
        lines = [
            f"  [{q.bloom_level.value}] {q.prompt[:80]}"
            for q in question_set.questions
        ]
        debug_logger.section("GENERATED QUESTIONS", "\n".join(lines))
    return question_set


def generation_prompt_version() -> str:
    return FULLTEXT_QUESTION_PROMPT_VERSION

import json
import re

from app.llm.openrouter_client import OpenRouterClient
from app.llm.prompts import QUESTION_PROMPT_VERSION, question_generation_prompt
from app.llm.schemas import QuestionSetOutput


_JSON_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json_payload(raw_response: str) -> dict:
    stripped = raw_response.strip()
    if not stripped:
        raise ValueError("Question generation returned empty response from LLM")

    candidates: list[str] = [stripped]
    fenced = _JSON_CODE_BLOCK_RE.findall(stripped)
    candidates.extend(block.strip() for block in fenced if block.strip())

    # Fallback: locate the largest JSON object segment in mixed text output.
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


async def generate_questions(cleaned_text: str, content_id: str) -> QuestionSetOutput:
    client = OpenRouterClient()
    prompt = question_generation_prompt(cleaned_text)
    response = await client.complete(prompt)
    payload = _extract_json_payload(response)
    question_set = QuestionSetOutput.model_validate(payload)
    question_set.content_id = content_id
    return question_set


def generation_prompt_version() -> str:
    return QUESTION_PROMPT_VERSION

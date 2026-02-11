import json

from app.llm.openrouter_client import OpenRouterClient
from app.llm.prompts import QUESTION_PROMPT_VERSION, question_generation_prompt
from app.llm.schemas import QuestionSetOutput


async def generate_questions(cleaned_text: str, content_id: str) -> QuestionSetOutput:
    client = OpenRouterClient()
    prompt = question_generation_prompt(cleaned_text)
    response = await client.complete(prompt)
    stripped = response.strip()
    if not stripped:
        raise ValueError("Question generation returned empty response from LLM")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        preview = stripped[:500]
        raise ValueError(
            "Question generation returned non-JSON output. "
            f"Response preview: {preview}"
        ) from exc
    question_set = QuestionSetOutput.model_validate(payload)
    question_set.content_id = content_id
    return question_set


def generation_prompt_version() -> str:
    return QUESTION_PROMPT_VERSION

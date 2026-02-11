import json

from app.llm.openrouter_client import OpenRouterClient
from app.llm.prompts import GRADING_PROMPT_VERSION, grading_prompt
from app.llm.schemas import GradingOutput


async def grade_answers(payload: str) -> GradingOutput:
    client = OpenRouterClient()
    prompt = grading_prompt(payload)
    response = await client.complete(prompt)
    data = json.loads(response)
    return GradingOutput.model_validate(data)


def grading_prompt_version() -> str:
    return GRADING_PROMPT_VERSION

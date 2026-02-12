QUESTION_PROMPT_VERSION = "v1"
GRADING_PROMPT_VERSION = "v1"


def question_generation_prompt(cleaned_text: str) -> str:
    return (
        "Generate 10 questions (5 recall, 5 explain) as strict JSON matching the schema. "
        "Include sources with quote, start_char, end_char. Text: "
        f"{cleaned_text}"
    )


def grading_prompt(payload: str) -> str:
    return (
        "Grade the following quiz answers strictly as JSON matching the schema. "
        f"Payload: {payload}"
    )

QUESTION_PROMPT_VERSION = "v1"
GRADING_PROMPT_VERSION = "v1"


def question_generation_prompt(cleaned_text: str) -> str:
    return (
        "Return ONLY valid JSON (no markdown, no code fences, no prose) with this shape: "
        "{\"content_id\":\"string\",\"questions\":[{\"question_id\":\"q1\","
        "\"question_type\":\"recall|explain\",\"prompt\":\"...\","
        "\"expected_answer\":\"...\",\"key_points\":[\"...\"],"
        "\"sources\":[{\"quote\":\"...\",\"start_char\":0,\"end_char\":1}]}]}. "
        "Generate exactly 10 questions: 5 recall and 5 explain. "
        "Each question must include at least one source snippet with quote/start_char/end_char offsets. "
        "Use only the provided text. Text: "
        f"{cleaned_text}"
    )


def grading_prompt(payload: str) -> str:
    return (
        "Grade the following quiz answers strictly as JSON matching the schema. "
        f"Payload: {payload}"
    )

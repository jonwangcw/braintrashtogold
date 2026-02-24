QUESTION_PROMPT_VERSION = "v1"
GRADING_PROMPT_VERSION = "v1"


def question_generation_prompt(cleaned_text: str, correction_hints: str | None = None) -> str:
    hints_section = ""
    if correction_hints:
        hints_section = (
            " Prioritize slide-confirmed terminology from these correction hints when phrasing questions and expected answers: "
            f"{correction_hints}."
        )
    return (
        "Return ONLY valid JSON (no markdown, no code fences, no prose) with this shape: "
        "{\"content_id\":\"string\",\"questions\":[{\"question_id\":\"q1\","
        "\"question_type\":\"recall|explain\",\"prompt\":\"...\","
        "\"expected_answer\":\"...\",\"key_points\":[\"...\"],"
        "\"sources\":[{\"quote\":\"...\",\"start_char\":0,\"end_char\":1}]}]}. "
        "Generate exactly 10 questions: 5 recall and 5 explain. "
        "Each question must include at least one source snippet with quote/start_char/end_char offsets. "
        "Use only the provided text."
        f"{hints_section} Text: {cleaned_text}"
    )


def grading_prompt(payload: str) -> str:
    return (
        "Grade the following quiz answers strictly as JSON matching the schema. "
        f"Payload: {payload}"
    )

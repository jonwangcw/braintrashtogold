QUESTION_PROMPT_VERSION = "v2"
GRADING_PROMPT_VERSION = "v1"
CONCEPT_EXTRACTION_PROMPT_VERSION = "v1"
CONCEPT_MERGE_PROMPT_VERSION = "v1"
PROBE_GENERATION_PROMPT_VERSION = "v1"


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
        "\"bloom_level\":\"remember|understand|apply|analyze|evaluate|create\","
        "\"concept_id\":\"c1\",\"prompt\":\"...\","
        "\"expected_answer\":\"...\",\"key_points\":[\"...\"],"
        "\"required_evidence_refs\":[\"ev1\"],"
        "\"sources\":[{\"evidence_id\":\"ev1\",\"quote\":\"...\",\"start_char\":0,\"end_char\":1}]}]}. "
        "Generate exactly 10 questions: 5 remember and 5 understand. "
        "Each question must include at least one source snippet and required evidence reference(s). "
        "Use only the provided text."
        f"{hints_section} Text: {cleaned_text}"
    )


def concept_extraction_prompt(cleaned_text: str) -> str:
    return (
        "Return ONLY valid JSON with this shape: "
        "{\"content_id\":\"string\",\"concepts\":[{\"concept_id\":\"c1\",\"concept_name\":\"...\","
        "\"summary\":\"...\",\"evidence\":[{\"evidence_id\":\"ev1\",\"quote\":\"...\","
        "\"start_char\":0,\"end_char\":1,\"chunk_index\":0}]}]}. "
        "Extract the most teachable concepts and attach concrete evidence spans from the transcript. "
        "Use exact quote snippets and offsets from the provided text. Text: "
        f"{cleaned_text}"
    )


def semantic_merge_decision_prompt(concepts_payload: str) -> str:
    return (
        "Return ONLY valid JSON with this shape: "
        "{\"actions\":[{\"action\":\"merge|keep_separate\",\"source_concept_id\":\"c2\","
        "\"target_concept_id\":\"c1\",\"rationale\":\"...\"}]}. "
        "Decide whether any concept ids are semantic duplicates and should be merged. "
        "Only merge when meaning is equivalent and evidence overlaps strongly. "
        f"Concepts: {concepts_payload}"
    )


def probe_generation_prompt(concept_payload: str, bloom_level: str, evidence_payload: str) -> str:
    return (
        "Return ONLY valid JSON with this shape: "
        "{\"question_id\":\"q1\",\"concept_id\":\"c1\","
        "\"bloom_level\":\"remember|understand|apply|analyze|evaluate|create\","
        "\"prompt\":\"...\",\"expected_answer\":\"...\",\"key_points\":[\"...\"],"
        "\"required_evidence_refs\":[\"ev1\"],"
        "\"sources\":[{\"evidence_id\":\"ev1\",\"quote\":\"...\",\"start_char\":0,\"end_char\":1}]}. "
        f"Generate one high-quality probe targeting Bloom level '{bloom_level}'. "
        "Ground the probe in required evidence references only. "
        f"Concept: {concept_payload}. Evidence: {evidence_payload}"
    )


def grading_prompt(payload: str) -> str:
    return (
        "Grade the following quiz answers strictly as JSON matching the schema. "
        f"Payload: {payload}"
    )

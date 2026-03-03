import json
import re
from collections.abc import Iterable

from app.llm.openrouter_client import OpenRouterClient
from app.llm.prompts import (
    QUESTION_PROMPT_VERSION,
    concept_extraction_prompt,
    probe_generation_prompt,
    semantic_merge_decision_prompt,
)
from app.llm.schemas import (
    BloomLevel,
    ConceptExtractionOutput,
    ConceptMergeDecisionOutput,
    ConceptOutput,
    ProbeGenerationOutput,
    QuestionOutput,
    QuestionSetOutput,
    SourceSnippet,
)
from app.processing.chunking import chunk_text


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


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _validate_source_offsets(sources: Iterable[SourceSnippet], cleaned_text: str) -> None:
    chunks = chunk_text(cleaned_text)
    for source in sources:
        if source.end_char > len(cleaned_text):
            raise ValueError(f"evidence span {source.evidence_id} exceeds cleaned text length")

        matching_chunks = [
            chunk
            for chunk in chunks
            if source.start_char >= chunk.start_char and source.end_char <= chunk.end_char
        ]
        if not matching_chunks:
            raise ValueError(f"evidence span {source.evidence_id} does not align to any transcript chunk")

        snippet = cleaned_text[source.start_char : source.end_char]
        if _normalize_whitespace(snippet) != _normalize_whitespace(source.quote):
            raise ValueError(f"evidence quote mismatch for {source.evidence_id}")


def _apply_semantic_merges(
    concepts: list[ConceptOutput],
    merge_decision: ConceptMergeDecisionOutput,
) -> list[ConceptOutput]:
    concept_map = {concept.concept_id: concept for concept in concepts}
    for action in merge_decision.actions:
        if action.action.value != "merge" or not action.target_concept_id:
            continue
        source = concept_map.get(action.source_concept_id)
        target = concept_map.get(action.target_concept_id)
        if source is None or target is None or source.concept_id == target.concept_id:
            continue
        target.evidence.extend(source.evidence)
        concept_map.pop(source.concept_id, None)
    return list(concept_map.values())


async def extract_concepts(cleaned_text: str, content_id: str) -> list[ConceptOutput]:
    client = OpenRouterClient()
    extraction_prompt = concept_extraction_prompt(cleaned_text)
    extraction_response = await client.complete(extraction_prompt)
    extraction_payload = _extract_json_payload(extraction_response)
    extracted = ConceptExtractionOutput.model_validate(extraction_payload)
    extracted.content_id = content_id

    for concept in extracted.concepts:
        _validate_source_offsets(concept.evidence, cleaned_text)

    merge_prompt = semantic_merge_decision_prompt(extracted.model_dump_json())
    merge_response = await client.complete(merge_prompt)
    merge_payload = _extract_json_payload(merge_response)
    merge_decision = ConceptMergeDecisionOutput.model_validate(merge_payload)
    merged_concepts = _apply_semantic_merges(extracted.concepts, merge_decision)

    if not merged_concepts:
        raise ValueError("No concepts remain after semantic merge decisions")

    for concept in merged_concepts:
        if not concept.evidence:
            raise ValueError(f"Concept {concept.concept_id} has no evidence after merge")

    return merged_concepts


async def generate_probe(
    concept: ConceptOutput,
    bloom_level: BloomLevel,
    evidence: list[SourceSnippet],
) -> QuestionOutput:
    if not evidence:
        raise ValueError("At least one evidence item is required to generate a probe")

    client = OpenRouterClient()
    prompt = probe_generation_prompt(
        concept_payload=concept.model_dump_json(),
        bloom_level=bloom_level.value,
        evidence_payload=json.dumps([item.model_dump() for item in evidence]),
    )
    response = await client.complete(prompt)
    payload = _extract_json_payload(response)
    probe = ProbeGenerationOutput.model_validate(payload)
    return QuestionOutput.model_validate(probe.model_dump())


async def generate_questions(
    cleaned_text: str,
    content_id: str,
    correction_hints: str | None = None,
) -> QuestionSetOutput:
    del correction_hints  # Pipeline now uses concept and probe prompts.
    concepts = await extract_concepts(cleaned_text, content_id)

    levels = ([BloomLevel.remember] * 5) + ([BloomLevel.understand] * 5)
    questions: list[QuestionOutput] = []
    for index, bloom_level in enumerate(levels):
        concept = concepts[index % len(concepts)]
        evidence = [
            SourceSnippet(
                evidence_id=item.evidence_id,
                quote=item.quote,
                start_char=item.start_char,
                end_char=item.end_char,
            )
            for item in concept.evidence
        ]
        generated = await generate_probe(concept, bloom_level, evidence)
        generated.question_id = f"q{index + 1}"
        generated.concept_id = concept.concept_id
        generated.bloom_level = bloom_level
        _validate_source_offsets(generated.sources, cleaned_text)
        questions.append(generated)

    question_set = QuestionSetOutput(content_id=content_id, questions=questions)
    return question_set


def generation_prompt_version() -> str:
    return QUESTION_PROMPT_VERSION

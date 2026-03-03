from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class BloomLevel(str, Enum):
    remember = "remember"
    understand = "understand"
    apply = "apply"
    analyze = "analyze"
    evaluate = "evaluate"
    create = "create"


class SourceSnippet(BaseModel):
    evidence_id: str
    quote: str
    start_char: int
    end_char: int

    @model_validator(mode="after")
    def validate_offsets(self) -> "SourceSnippet":
        if self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("source snippet offsets must be non-negative and end_char must be greater than start_char")
        return self


class QuestionOutput(BaseModel):
    question_id: str
    bloom_level: BloomLevel
    concept_id: str
    prompt: str
    expected_answer: str
    key_points: list[str] = Field(min_length=1)
    required_evidence_refs: list[str] = Field(min_length=1)
    sources: list[SourceSnippet] = Field(min_length=1)

    @field_validator("required_evidence_refs")
    @classmethod
    def validate_required_evidence_refs(cls, value: list[str]) -> list[str]:
        deduped = list(dict.fromkeys(value))
        if len(deduped) != len(value):
            raise ValueError("required_evidence_refs must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_evidence_refs_are_known(self) -> "QuestionOutput":
        source_ids = {source.evidence_id for source in self.sources}
        unknown = [ref for ref in self.required_evidence_refs if ref not in source_ids]
        if unknown:
            raise ValueError(f"required_evidence_refs contains unknown evidence ids: {unknown}")
        return self


class QuestionSetOutput(BaseModel):
    content_id: str
    questions: list[QuestionOutput]

    @field_validator("questions")
    @classmethod
    def validate_question_count(cls, value: list[QuestionOutput]) -> list[QuestionOutput]:
        if len(value) != 10:
            raise ValueError("question set must contain exactly 10 questions")
        remember = [q for q in value if q.bloom_level == BloomLevel.remember]
        understand = [q for q in value if q.bloom_level == BloomLevel.understand]
        if len(remember) != 5 or len(understand) != 5:
            raise ValueError("question set must contain 5 remember and 5 understand questions")
        return value


class ConceptEvidenceSpan(BaseModel):
    evidence_id: str
    quote: str
    start_char: int
    end_char: int
    chunk_index: int


class ConceptOutput(BaseModel):
    concept_id: str
    concept_name: str
    summary: str
    evidence: list[ConceptEvidenceSpan] = Field(min_length=1)


class ConceptExtractionOutput(BaseModel):
    content_id: str
    concepts: list[ConceptOutput] = Field(min_length=1)


class MergeDecisionAction(str, Enum):
    merge = "merge"
    keep_separate = "keep_separate"


class MergeActionOutput(BaseModel):
    action: MergeDecisionAction
    source_concept_id: str
    target_concept_id: str | None = None
    rationale: str

    @model_validator(mode="after")
    def validate_target_when_merge(self) -> "MergeActionOutput":
        if self.action == MergeDecisionAction.merge and not self.target_concept_id:
            raise ValueError("target_concept_id is required when action=merge")
        return self


class ConceptMergeDecisionOutput(BaseModel):
    actions: list[MergeActionOutput] = Field(default_factory=list)


class ProbeGenerationOutput(BaseModel):
    question_id: str
    concept_id: str
    bloom_level: BloomLevel
    prompt: str
    expected_answer: str
    key_points: list[str] = Field(min_length=1)
    required_evidence_refs: list[str] = Field(min_length=1)
    sources: list[SourceSnippet] = Field(min_length=1)

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SourceSnippet(BaseModel):
    quote: str
    start_char: int
    end_char: int


class QuestionOutput(BaseModel):
    question_id: str
    question_type: Literal["recall", "explain"]
    prompt: str
    expected_answer: str
    key_points: list[str] = Field(min_length=1)
    sources: list[SourceSnippet] = Field(min_length=1)


class QuestionSetOutput(BaseModel):
    content_id: str
    questions: list[QuestionOutput]

    @field_validator("questions")
    @classmethod
    def validate_question_count(cls, value: list[QuestionOutput]) -> list[QuestionOutput]:
        if len(value) != 10:
            raise ValueError("question set must contain exactly 10 questions")
        recall = [q for q in value if q.question_type == "recall"]
        explain = [q for q in value if q.question_type == "explain"]
        if len(recall) != 5 or len(explain) != 5:
            raise ValueError("question set must contain 5 recall and 5 explain questions")
        return value

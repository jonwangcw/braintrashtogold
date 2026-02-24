import json

from sqlalchemy.orm import Session

from app.db import models
from app.llm.grading import grade_answers
from app.llm.question_gen import generate_questions, generation_prompt_version
from app.llm.schemas import GradingOutput


async def create_question_set(
    session: Session,
    content_id: int,
    cleaned_text: str,
    correction_hints: str | None = None,
    kind: models.QuestionSetKind = models.QuestionSetKind.scheduled,
) -> models.QuestionSet:
    print(
        f"[DEBUG] create_question_set:start content_id={content_id} kind={kind} cleaned_text_len={len(cleaned_text)}"
    )
    generated = await generate_questions(cleaned_text, str(content_id), correction_hints=correction_hints)
    print(f"[DEBUG] create_question_set:generated questions_count={len(generated.questions)}")
    for index, question in enumerate(generated.questions, start=1):
        preview = question.prompt.replace("\n", " ")[:200]
        print(
            f"[DEBUG] create_question_set:question[{index}] "
            f"type={question.question_type} prompt={preview}"
        )

    question_set = models.QuestionSet(
        content_id=content_id,
        kind=kind,
        generator_model="openrouter",
        generation_prompt_version=generation_prompt_version(),
    )
    session.add(question_set)
    session.flush()

    for index, question in enumerate(generated.questions):
        session.add(
            models.Question(
                question_set_id=question_set.id,
                question_index=index,
                question_type=question.question_type,
                prompt=question.prompt,
                expected_answer=question.expected_answer,
                key_points_json=json.dumps(question.key_points),
                sources_json=json.dumps([source.model_dump() for source in question.sources]),
            )
        )

    session.commit()
    session.refresh(question_set)
    print(f"[DEBUG] create_question_set:committed question_set_id={question_set.id}")
    return question_set


async def grade_quiz(payload: str) -> GradingOutput:
    return await grade_answers(payload)

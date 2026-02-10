from sqlalchemy.orm import Session

from app.llm.grading import grade_answers
from app.llm.question_gen import generate_questions, generation_prompt_version
from app.llm.schemas import GradingOutput


async def create_question_set(session: Session, content_id: int, cleaned_text: str) -> int:
    question_set = await generate_questions(cleaned_text, str(content_id))
    db_set = session.execute(
        "INSERT INTO question_sets (content_id, kind, generated_at, generator_model, generation_prompt_version) "
        "VALUES (:content_id, :kind, CURRENT_TIMESTAMP, :generator_model, :prompt_version)",
        {
            "content_id": content_id,
            "kind": "scheduled",
            "generator_model": "openrouter",
            "prompt_version": generation_prompt_version(),
        },
    )
    session.commit()
    return db_set.lastrowid


async def grade_quiz(payload: str) -> GradingOutput:
    return await grade_answers(payload)

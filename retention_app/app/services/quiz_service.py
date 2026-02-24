import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.llm.question_gen import generate_questions, generation_prompt_version
from app.scheduling import strategy_v1


def get_latest_question_set(
    session: Session,
    content_id: int,
    kind: models.QuestionSetKind,
) -> models.QuestionSet | None:
    return session.execute(
        select(models.QuestionSet)
        .where(models.QuestionSet.content_id == content_id, models.QuestionSet.kind == kind)
        .order_by(models.QuestionSet.generated_at.desc())
    ).scalars().first()


def ensure_question_set(
    session: Session,
    content_id: int,
    kind: models.QuestionSetKind,
) -> models.QuestionSet:
    question_set = get_latest_question_set(session, content_id, kind)
    if question_set is not None:
        return question_set

    question_set = models.QuestionSet(
        content_id=content_id,
        kind=kind,
        generator_model="placeholder",
        generation_prompt_version="v0",
    )
    session.add(question_set)
    session.commit()
    session.refresh(question_set)
    return question_set


def create_quiz_attempt(
    session: Session,
    content_id: int,
    kind: models.QuizAttemptKind,
) -> models.QuizAttempt:
    question_set = ensure_question_set(session, content_id, models.QuestionSetKind(kind.value))
    attempt = models.QuizAttempt(
        content_id=content_id,
        question_set_id=question_set.id,
        kind=kind,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def complete_quiz_attempt(
    session: Session,
    quiz_attempt_id: int,
    comfort_rating: int | None = None,
) -> models.QuizAttempt:
    attempt = session.get(models.QuizAttempt, quiz_attempt_id)
    if attempt is None:
        raise ValueError("quiz attempt not found")

    attempt.submitted_at = datetime.utcnow()

    if attempt.kind == models.QuizAttemptKind.scheduled:
        if comfort_rating is None:
            raise ValueError("comfort_rating is required for scheduled quizzes")
        if comfort_rating < 1 or comfort_rating > 5:
            raise ValueError("comfort_rating must be between 1 and 5")

        scaled_score = float(comfort_rating * 2)
        attempt.total_score = scaled_score

        state = session.get(models.ScheduleState, attempt.content_id)
        if state is not None and not state.is_terminated:
            scheduled_attempt_count = session.execute(
                select(func.count(models.QuizAttempt.id)).where(
                    models.QuizAttempt.content_id == attempt.content_id,
                    models.QuizAttempt.kind == models.QuizAttemptKind.scheduled,
                    models.QuizAttempt.submitted_at.is_not(None),
                    models.QuizAttempt.id != attempt.id,
                )
            ).scalar_one()
            decision = strategy_v1.next_state(
                step_index=state.step_index,
                last_completed_at=attempt.submitted_at,
                comfort_level=comfort_rating,
                scheduled_attempt_count=scheduled_attempt_count,
            )
            state.step_index = decision.next_step_index
            state.next_due_at = decision.next_due_at
            state.last_scheduled_quiz_at = attempt.submitted_at
            state.last_score = scaled_score
            state.is_terminated = decision.terminate
            session.add(state)

    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


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

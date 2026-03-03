import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .engine import Base


class ContentType(str, enum.Enum):
    youtube = "youtube"
    rss_episode = "rss_episode"
    pdf = "pdf"
    webpage = "webpage"


class ContentStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    error = "error"


class QuestionSetKind(str, enum.Enum):
    scheduled = "scheduled"
    practice = "practice"


class QuestionType(str, enum.Enum):
    recall = "recall"
    explain = "explain"


class QuizAttemptKind(str, enum.Enum):
    scheduled = "scheduled"
    practice = "practice"




class ProbeStatus(str, enum.Enum):
    active = "active"
    superseded = "superseded"


class ReviewRating(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class NotificationKind(str, enum.Enum):
    email = "email"
    system = "system"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[ContentType] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[ContentStatus] = mapped_column(String(20), default=ContentStatus.pending)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    text: Mapped["ContentText"] = relationship("ContentText", back_populates="content", uselist=False)
    question_sets: Mapped[list["QuestionSet"]] = relationship("QuestionSet", back_populates="content")
    schedule_state: Mapped["ScheduleState"] = relationship(
        "ScheduleState", back_populates="content", uselist=False
    )


class ContentText(Base):
    __tablename__ = "content_text"

    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), primary_key=True)
    cleaned_text: Mapped[str] = mapped_column(Text)
    raw_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text_corpus: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_annotations: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    content: Mapped[Content] = relationship("Content", back_populates="text")


class QuestionSet(Base):
    __tablename__ = "question_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    kind: Mapped[QuestionSetKind] = mapped_column(String(20))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    generator_model: Mapped[str] = mapped_column(String(100))
    generation_prompt_version: Mapped[str] = mapped_column(String(50))

    content: Mapped[Content] = relationship("Content", back_populates="question_sets")
    questions: Mapped[list["Question"]] = relationship("Question", back_populates="question_set")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_set_id: Mapped[int] = mapped_column(ForeignKey("question_sets.id"))
    question_index: Mapped[int] = mapped_column(Integer)
    question_type: Mapped[QuestionType] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str] = mapped_column(Text)
    key_points_json: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    question_set: Mapped[QuestionSet] = relationship("QuestionSet", back_populates="questions")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    question_set_id: Mapped[int] = mapped_column(ForeignKey("question_sets.id"))
    kind: Mapped[QuizAttemptKind] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comfort_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_attempt_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grader_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grading_prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    answers: Mapped[list["Answer"]] = relationship("Answer", back_populates="quiz_attempt")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    user_answer: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    feedback: Mapped[str] = mapped_column(Text)
    graded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    quiz_attempt: Mapped[QuizAttempt] = relationship("QuizAttempt", back_populates="answers")


class ScheduleState(Base):
    __tablename__ = "schedule_state"

    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), primary_key=True)
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_scheduled_quiz_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_terminated: Mapped[bool] = mapped_column(Boolean, default=False)

    content: Mapped[Content] = relationship("Content", back_populates="schedule_state")




class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConceptProbe(Base):
    __tablename__ = "concept_probes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"))
    prompt: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProbeStatus] = mapped_column(String(20), default=ProbeStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConceptSchedule(Base):
    __tablename__ = "concept_schedule"

    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), primary_key=True)
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_terminated: Mapped[bool] = mapped_column(Boolean, default=False)


class ReviewEvent(Base):
    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"))
    probe_id: Mapped[int] = mapped_column(ForeignKey("concept_probes.id"))
    self_comfort: Mapped[int] = mapped_column(Integer)
    correctness: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    kind: Mapped[NotificationKind] = mapped_column(String(20))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[NotificationStatus] = mapped_column(String(20), default=NotificationStatus.pending)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

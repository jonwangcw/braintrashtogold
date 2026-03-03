import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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


class BloomLevel(str, enum.Enum):
    knowledge = "Knowledge"
    comprehension = "Comprehension"
    application = "Application"
    analysis = "Analysis"
    synthesis = "Synthesis"
    evaluation = "Evaluation"


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
    segments: Mapped[list["ContentSegment"]] = relationship("ContentSegment", back_populates="content")
    concept_evidence: Mapped[list["ConceptEvidence"]] = relationship("ConceptEvidence", back_populates="content")


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


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    kind: Mapped[NotificationKind] = mapped_column(String(20))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[NotificationStatus] = mapped_column(String(20), default=NotificationStatus.pending)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContentSegment(Base):
    __tablename__ = "content_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    start_char: Mapped[int] = mapped_column(Integer)
    end_char: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    content: Mapped[Content] = relationship("Content", back_populates="segments")
    evidence_links: Mapped[list["ConceptEvidence"]] = relationship("ConceptEvidence", back_populates="segment")


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("user_id", "canonical_name", name="uq_concepts_user_canonical"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int | None] = mapped_column(ForeignKey("contents.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_name: Mapped[str] = mapped_column(String(255), index=True)
    summary: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    evidence_links: Mapped[list["ConceptEvidence"]] = relationship("ConceptEvidence", back_populates="concept")
    schedule: Mapped["ConceptSchedule"] = relationship("ConceptSchedule", back_populates="concept", uselist=False)
    probes: Mapped[list["QuestionProbe"]] = relationship("QuestionProbe", back_populates="concept")
    review_events: Mapped[list["ReviewEvent"]] = relationship("ReviewEvent", back_populates="concept")


class ConceptProbe(Base):
    __tablename__ = "concept_probes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProbeStatus] = mapped_column(String(20), default=ProbeStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuestionProbe(Base):
    __tablename__ = "question_probes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), index=True)
    bloom_level: Mapped[BloomLevel] = mapped_column(String(32), default=BloomLevel.knowledge)
    prompt: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generation_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    concept: Mapped[Concept] = relationship("Concept", back_populates="probes")
    review_events: Mapped[list["ReviewEvent"]] = relationship("ReviewEvent", back_populates="question_probe")


class ConceptEvidence(Base):
    __tablename__ = "concept_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), index=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), index=True)
    content_segment_id: Mapped[int | None] = mapped_column(ForeignKey("content_segments.id"), index=True, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    span_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    span_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_strength: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    concept: Mapped[Concept] = relationship("Concept", back_populates="evidence_links")
    content: Mapped[Content] = relationship("Content", back_populates="concept_evidence")
    segment: Mapped[ContentSegment | None] = relationship("ContentSegment", back_populates="evidence_links")


class ConceptMergeAudit(Base):
    __tablename__ = "concept_merge_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_concept_name: Mapped[str] = mapped_column(String(255))
    target_concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), index=True)
    similarity_score: Mapped[float] = mapped_column(Float)
    rationale_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConceptSchedule(Base):
    __tablename__ = "concept_schedule"
    __table_args__ = (Index("ix_concept_schedule_user_due", "user_id", "due_at"),)

    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)

    step_index: Mapped[int] = mapped_column(Integer, default=0)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_terminated: Mapped[bool] = mapped_column(Boolean, default=False)

    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    reinforcement_count: Mapped[int] = mapped_column(Integer, default=0)

    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    bloom_stage: Mapped[BloomLevel] = mapped_column(String(32), default=BloomLevel.knowledge)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    concept: Mapped[Concept] = relationship("Concept", back_populates="schedule")


class ReviewEvent(Base):
    __tablename__ = "review_events"
    __table_args__ = (Index("ix_review_events_concept_created", "concept_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), index=True)

    probe_id: Mapped[int | None] = mapped_column(ForeignKey("concept_probes.id"), nullable=True)
    question_probe_id: Mapped[int | None] = mapped_column(ForeignKey("question_probes.id"), nullable=True)

    self_comfort: Mapped[int] = mapped_column(Integer)
    correctness: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    concept: Mapped[Concept] = relationship("Concept", back_populates="review_events")
    question_probe: Mapped[QuestionProbe | None] = relationship("QuestionProbe", back_populates="review_events")

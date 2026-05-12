"""Application tracking database model."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# All application states per blueprint
APPLICATION_STATES = [
    "discovered",
    "parsed",
    "matched",
    "shortlisted",
    "resume_selected",
    "tailored",
    "cover_letter_ready",
    "ready_to_apply",
    "queued",
    "applying",
    "blocked_exception_created",
    "auto_resolution_running",
    "ai_resolution_running",
    "operator_required",
    "operator_in_progress",
    "resolved_retry_ready",
    "submitted",
    "submission_unconfirmed",
    "failed_retryable",
    "failed_manual",
    "duplicate",
    "rejected",
    "response_received",
    "interview_requested",
    "abandoned",
]


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A job application submitted or queued for submission."""

    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_application_status", "status"),
        Index("ix_application_job_id", "job_id"),
        Index("ix_application_candidate_id", "candidate_id"),
    )

    # Foreign keys
    candidate_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    resume_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("resumes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Application state (expanded per blueprint)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="discovered")
    apply_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="review")

    # Scoring
    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Match scores (individual components)
    skill_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    title_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    experience_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    visa_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    interview_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Documents
    cover_letter_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tailored_resume_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Follow-up tracking
    follow_up_count: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    last_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    browser_screenshots: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Portal info
    portal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    confirmation_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    candidate: Mapped["Candidate"] = relationship(back_populates="applications")  # noqa: F821
    job: Mapped["Job"] = relationship(back_populates="applications")  # noqa: F821
    resume: Mapped["Resume | None"] = relationship(back_populates="applications")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, job_id={self.job_id}, status='{self.status}')>"

"""Exception resolution attempt tracking database model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExceptionResolutionAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks each resolution attempt for an exception case."""

    __tablename__ = "exception_resolution_attempts"
    __table_args__ = (
        Index("ix_attempt_exception", "exception_case_id"),
    )

    # Foreign Key
    exception_case_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("exception_cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Attempt details
    attempt_number: Mapped[int] = mapped_column(String(10), nullable=False)
    resolution_method: Mapped[str] = mapped_column(String(50), nullable=False)
    # Options: auto_retry, new_session, proxy_switch, delayed_retry,
    #         alternate_workflow, ai_solved, human_input

    # Resolution type
    resolution_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Options: auto, ai, human

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # Options: running, success, failed, abandoned

    # Details
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What action was attempted

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Error if failed

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # AI confidence (if AI-assisted)
    ai_confidence_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_confidence_after: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Results
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    proxy_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<ExceptionResolutionAttempt(id={self.id}, method='{self.resolution_method}', case={self.exception_case_id})>"
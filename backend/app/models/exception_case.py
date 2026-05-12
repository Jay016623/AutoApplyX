"""Exception case database model for tracking failed applications and errors."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExceptionCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks blocked/failed applications that need resolution."""

    __tablename__ = "exception_cases"
    __table_args__ = (
        Index("ix_exception_case_status", "status"),
        Index("ix_exception_case_priority", "priority"),
        Index("ix_exception_case_sla_deadline", "sla_deadline"),
    )

    # Foreign Keys
    candidate_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Portal/Source info
    portal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Options: linkedin, indeed, dice, monster, company_portal, ats

    # Exception details
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Options: otp_required, captcha_blocked, login_failed, form_unrecognized,
    #         data_missing, resume_upload_failed, submission_failed, unknown_error

    stage_failed: Mapped[str] = mapped_column(String(50), nullable=False)
    # Options: login, job_page, form_fill, resume_upload, cover_letter, 
    #         screening_questions, final_submit, confirmation

    # Error details
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Screenshots/DOM
    screenshot_urls: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # JSON array of screenshot URLs

    dom_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # DOM snapshot for debugging

    # Resolution tracking
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="created")
    # Options: created, auto_resolving, ai_resolving, operator_required,
    #         operator_in_progress, resolved_retry, resolved_permanent, abandoned

    resolution_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Options: none, auto_retry, new_session, proxy_switch, delayed_retry,
    #         alternate_workflow, ai_solved, human_solved

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(String(10), nullable=False, default=5)

    # AI confidence
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # AI's confidence in resolving this case

    # Time tracking
    time_blocked_minutes: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Value scoring (for priority)
    job_salary: Mapped[str | None] = mapped_column(String(50), nullable=True)
    interview_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Priority (calculated)
    priority: Mapped[int] = mapped_column(String(10), nullable=False, default=5)
    # 1-10, calculated from salary, probability, SLA risk

    # Resolution notes
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resolved timestamp
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ExceptionCase(id={self.id}, type='{self.exception_type}', status='{self.status}')>"
"""Worker job tracking database model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkerJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks background worker task executions."""

    __tablename__ = "worker_jobs"
    __table_args__ = (
        Index("ix_worker_job_type", "worker_type"),
        Index("ix_worker_job_status", "status"),
    )

    # Worker Identification
    worker_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Options: job_scraper, jd_parser, match, resume_tailor, cover_letter, 
    #         application, exception_intake, auto_resolution, ai_exception_solver,
    #         otp, captcha, login_recovery, missing_data, email_review, 
    #         followup, reporting, learning, retry, health_check

    # Job Details
    job_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON string containing job-specific data

    # Execution Tracking
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    # Options: queued, running, completed, failed, retrying, cancelled

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Retry Logic
    retry_count: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(String(10), nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Priority (higher = more urgent)
    priority: Mapped[int] = mapped_column(String(10), nullable=False, default=5)
    # Range: 1-10

    # Results
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON string with results

    # Timing
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<WorkerJob(id={self.id}, worker_type='{self.worker_type}', status='{self.status}')>"
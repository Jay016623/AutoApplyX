"""Daily metrics tracking database model."""

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DailyMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Daily aggregated metrics for KPI tracking."""

    __tablename__ = "daily_metrics"
    __table_args__ = (
        Index("ix_daily_metric_date", "date"),
    )

    # Date (partition key for daily data)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    # Format: YYYY-MM-DD

    # Application Metrics
    applications_submitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applications_queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applications_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applications_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Per-Candidate Breakdown (JSON for flexibility)
    applications_by_candidate: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # JSON: {"candidate_id1": 5, "candidate_id2": 3}

    # Job Discovery Metrics
    jobs_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Follow-Up Metrics
    follow_ups_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    responses_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interview_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Portal Performance
    portal_applications: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # JSON: {"linkedin": 10, "indeed": 5, "dice": 3}

    portal_success_rates: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # JSON: {"linkedin": 0.8, "indeed": 0.6}

    # Friction Metrics
    captcha_encountered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    otp_required: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    otp_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Exception/Error Metrics
    exceptions_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exceptions_resolved_auto: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exceptions_resolved_ai: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exceptions_resolved_human: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_resolution_time_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Human Touch Metrics
    operator_tasks_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    human_touch_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    automation_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Resume Performance
    resume_performance: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # JSON: {"resume_id1": {"submitted": 5, "interviews": 2}}

    # Worker Health
    worker_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # LLM Usage
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    def __repr__(self) -> str:
        return f"<DailyMetric(date={self.date})>"
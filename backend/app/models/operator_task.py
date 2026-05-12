"""Operator task database model for human-in-the-loop resolution."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OperatorTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tasks that require human operator intervention."""

    __tablename__ = "operator_tasks"
    __table_args__ = (
        Index("ix_operator_task_status", "status"),
        Index("ix_operator_task_assignee", "assignee"),
        Index("ix_operator_task_priority", "priority"),
    )

    # Foreign Keys
    exception_case_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("exception_cases.id", ondelete="CASCADE"),
        nullable=True,
    )

    candidate_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    application_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Task details
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Options: otp_entry, captcha_entry, form_fill, login_fix,
    #         data_confirmation, resume_generation, email_response

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Options: pending, in_progress, completed, cancelled

    # Priority
    priority: Mapped[int] = mapped_column(String(10), nullable=False, default=5)
    # 1-10, higher is more urgent

    # Assignment
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Operator username

    # Due
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Work
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Step-by-step instructions

    resolution_data: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # JSON with resolution data entered by operator

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<OperatorTask(id={self.id}, type='{self.task_type}', status='{self.status}')>"
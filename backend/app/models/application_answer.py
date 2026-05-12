"""Application answers database model for smart question answering."""

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ApplicationAnswer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pre-approved answers for recurring application questions."""

    __tablename__ = "application_answers"
    __table_args__ = (
        Index("ix_answer_candidate", "candidate_id"),
        Index("ix_answer_question_key", "question_key"),
    )

    # Foreign Keys
    candidate_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Question Identification
    question_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # Standardized keys for common questions:
    # - authorized_to_work
    # - need_sponsorship
    # - expected_salary
    # - notice_period
    # - willing_to_relocate
    # - years_sql
    # - years_python
    # - open_to_contract
    # - open_to_onsite
    # - highest_education
    # - work_authorize_disclosure
    
    question_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Original question text for reference

    # Answer Data
    answer_value: Mapped[str] = mapped_column(Text, nullable=False)
    # The approved answer (text, number as string, or choice)
    
    answer_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    # Options: text, number, boolean, choice

    # Validation
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Usage
    times_used: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    last_used_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    candidate: Mapped["Candidate"] = relationship(back_populates="application_answers")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ApplicationAnswer(id={self.id}, question_key='{self.question_key}', candidate_id={self.candidate_id})>"
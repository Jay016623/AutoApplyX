"""Candidate database model."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Candidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate profile for the AutoApplyX system."""

    __tablename__ = "candidates"
    __table_args__ = (
        Index("ix_candidate_status", "status"),
        Index("ix_candidate_readiness", "readiness_score"),
    )

    # Basic Info
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # Options: active, paused, archived, onboarding

    # Read the full blueprint context first with readiness_score determining if candidate is ready for automation
    readiness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Visa / Work Authorization
    visa_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Options: us_citizen, green_card, h1b, l1, opt, cpt, other, unknown
    needs_sponsorship: Mapped[bool] = mapped_column(Boolean, default=False)
    visa_expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Salary Expectations
    salary_min: Mapped[int | None] = mapped_column(String(20), nullable=True)
    salary_max: Mapped[int | None] = mapped_column(String(20), nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    notice_period_days: Mapped[int | None] = mapped_column(String(10), nullable=True)

    # Target Roles (primary job targets)
    target_role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_role_2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_role_3: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Location Preferences
    preferred_locations: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Stored as JSON array: ["New York, NY", "San Francisco, CA", "Remote"]

    # Work Type Preferences
    remote_preference: Mapped[str] = mapped_column(String(20), nullable=False, default="any")
    # Options: remote, hybrid, onsite, any

    employment_type_preference: Mapped[str] = mapped_column(String(20), nullable=False, default="any")
    # Options: full_time, part_time, contract, any

    # Availability
    available_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    available_now: Mapped[bool] = mapped_column(Boolean, default=True)

    # Resume info (primary resume for applications)
    primary_resume_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    # Additional Profile Data
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_experience: Mapped[int | None] = mapped_column(String(10), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Application tracking
    daily_apply_limit: Mapped[int] = mapped_column(String(10), nullable=False, default=10)
    total_applications: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    applications_today: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    last_application_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Skill Confidence Matrix - stored as JSON for flexibility
    # Structure: {"Python": 5, "SQL": 4, "React": 3, "AWS": 4}
    # Scale: 1-5 where 5 = expert
    skill_confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Application Answer Bank - pre-approved answers for repeated questions
    # Structure: {"authorized_to_work": "Yes", "need_sponsorship": "No", "salary_expectation": "120000"}
    answer_bank: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Portal Accounts - stored candidate credentials for job sites
    # Structure: {"linkedin": {"username": "...", "password": "..."}, "indeed": {...}}
    portal_accounts: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # === Relationships ===
    applications: Mapped[list["Application"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    portal_accounts_rel: Mapped[list["PortalAccount"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    application_answers: Mapped[list["ApplicationAnswer"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Candidate(id={self.id}, name='{self.first_name} {self.last_name}', email='{self.email}')>"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
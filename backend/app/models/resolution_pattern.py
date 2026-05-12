"""Resolution pattern database model for learning from solved exceptions."""

from sqlalchemy import Boolean, Float, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ResolutionPattern(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stores successful resolution patterns for future reference."""

    __tablename__ = "resolution_patterns"
    __table_args__ = (
        Index("ix_pattern_exception_type", "exception_type"),
        Index("ix_pattern_portal", "portal"),
    )

    # Pattern identification
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Which type of exception this resolves

    portal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Which portal (if specific)

    stage_failed: Mapped[str] = mapped_column(String(50), nullable=False)
    # At which stage

    # Pattern details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resolution steps (stored as JSON for flexibility)
    steps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # ["1. Click login button", "2. Wait for redirect", "3. Enter OTP"]

    # Conditions that trigger this pattern
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # {"error_code": "OTP_001", "portal": "linkedin"}

    # Success metrics
    success_count: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Success rate threshold to be recommended
    min_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    # Must have 70%+ success to be auto-recommended

    # Auto-applicable?
    is_auto_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    # Can this pattern be applied automatically?

    # Last used
    last_used_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Average resolution time
    avg_resolution_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Active?
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<ResolutionPattern(id={self.id}, type='{self.exception_type}', portal='{self.portal}')>"


# Additional tracking events

class CaptchaEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks captcha encounters for analytics."""

    __tablename__ = "captcha_events"
    __table_args__ = (
        Index("ix_captcha_portal", "portal"),
    )

    candidate_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    application_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    portal: Mapped[str] = mapped_column(String(50), nullable=False)

    captcha_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Options: image, checkbox, slider, recaptcha, hcaptcha, custom

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="encountered")
    # Options: encountered, bypassed, failed, operator_solved

    resolution_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<CaptchaEvent(id={self.id}, type='{self.captcha_type}')>"


class OTPEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks OTP encounters for analytics."""

    __tablename__ = "otp_events"
    __table_args__ = (
        Index("ix_otp_portal", "portal"),
    )

    candidate_id: Mapped[str | None] = mapped_column(String, nullable=True)
    application_id: Mapped[str | None] = mapped_column(String, nullable=True)

    portal: Mapped[str] = mapped_column(String(50), nullable=False)

    otp_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Options: email, sms, authenticator

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    # Options: requested, auto_fetched, manual_entry, failed, expired

    resolution_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Timing
    requested_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Source email (if email OTP)
    source_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<OTPEvent(id={self.id}, type='{self.otp_type}', portal='{self.portal}')>"
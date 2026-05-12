"""Portal account database model for candidate authentication on job sites."""

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PortalAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stores candidate credentials for job search portals."""

    __tablename__ = "portal_accounts"
    __table_args__ = (
        Index("ix_portal_account_candidate", "candidate_id"),
        Index("ix_portal_accountPortal", "portal"),
    )

    # Foreign Keys
    candidate_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Portal Identification
    portal: Mapped[str] = mapped_column(String(50), nullable=False)
    # Options: linkedin, indeed, dice, monster, glassdoor, ziprecruiter, glassdoor, company_portal, ats

    # Credentials (encrypted storage recommended in production)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Session tokens (for session reuse)
    session_token: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    session_expires_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Account Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[str | None] = mapped_column(String(50), nullable=True)
    login_attempts: Mapped[int] = mapped_column(String(10), nullable=False, default=0)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Portal-specific data
    portal_user_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Store the platform-specific user ID

    # Notes
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships (defined in Candidate model)
    # candidate: Mapped["Candidate"] = relationship(back_populates="portal_accounts_rel")

    def __repr__(self) -> str:
        return f"<PortalAccount(id={self.id}, portal='{self.portal}', candidate_id={self.candidate_id})>"
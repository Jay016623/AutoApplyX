"""Login Recovery System - Handle portal login failures and recovery.

Per blueprint:
- Credential vault
- Encrypted passwords
- Session reuse
- Failed login retry
- Password reset flow (if approved)
- Blocked account detection
- Portal health scoring
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.portal_account import PortalAccount

logger = structlog.get_logger(__name__)


class LoginStatus(str, Enum):
    """Login status."""
    SUCCESS = "success"
    FAILED = "failed"
    LOCKED = "locked"
    NEEDS_OTP = "needs_otp"
    NEEDS_CAPTCHA = "needs_captcha"
    PASSWORD_RESET = "password_reset"
    SESSION_REUSED = "session_reused"


class LoginFailureReason(str, Enum):
    """Reasons for login failure."""
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    OTP_REQUIRED = "otp_required"
    CAPTCHA_REQUIRED = "captcha_required"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMITED = "rate_limited"
    IP_BLOCKED = "ip_blocked"
    UNKNOWN = "unknown"


# Portal login configuration
PORTAL_LOGIN_CONFIG = {
    "linkedin": {
        "login_url": "https://www.linkedin.com/login",
        "session_cookie": "li_at",
        "max_retries": 3,
        "rate_limit_window": 60,  # minutes
    },
    "indeed": {
        "login_url": "https://secure.indeed.com/auth",
        "session_cookie": "indeed_session",
        "max_retries": 3,
        "rate_limit_window": 30,
    },
    "dice": {
        "login_url": "https://www.dice.com/diceapi/AuthenticationServlet",
        "session_cookie": "DICESESSION",
        "max_retries": 2,
        "rate_limit_window": 60,
    },
    "monster": {
        "login_url": "https://www.monster.com/login",
        "session_cookie": "MONSTER_SESSION",
        "max_retries": 3,
        "rate_limit_window": 30,
    },
}


async def get_login_config(portal: str) -> dict[str, Any]:
    """Get login configuration for a portal.
    
    Args:
        portal: Portal name.
    
    Returns:
        Login config or default.
    """
    return PORTAL_LOGIN_CONFIG.get(portal, {
        "login_url": "",
        "session_cookie": "",
        "max_retries": 3,
        "rate_limit_window": 60,
    })


async def check_session_valid(
    session_token: str,
    session_expires_at: str | None,
) -> bool:
    """Check if session token is still valid.
    
    Args:
        session_token: Session token.
        session_expires_at: Expiry timestamp string.
    
    Returns:
        True if valid.
    """
    if not session_token:
        return False
    
    if not session_expires_at:
        # No expiry - assume valid
        return True
    
    try:
        # Parse expiry
        expires = datetime.fromisoformat(session_expires_at.replace("Z", "+00:00"))
        if datetime.now() > expires:
            return False
    except (ValueError, AttributeError):
        pass
    
    return True


async def get_portal_account(
    db: AsyncSession,
    candidate_id: str,
    portal: str,
) -> PortalAccount | None:
    """Get candidate's portal account.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        portal: Portal name.
    
    Returns:
        PortalAccount or None.
    """
    result = await db.execute(
        select(PortalAccount)
        .where(PortalAccount.candidate_id == candidate_id)
        .where(PortalAccount.portal == portal)
    )
    return result.scalar_one_or_none()


async def authenticate_portal(
    db: AsyncSession,
    candidate_id: str,
    portal: str,
    username: str,
    password: str,
) -> dict[str, Any]:
    """Attempt to authenticate with a portal.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        portal: Portal name.
        username: Account username.
        password: Account password.
    
    Returns:
        Authentication result.
    """
    # Get portal config
    config = await get_login_config(portal)
    
    # Get or create portal account
    account = await get_portal_account(db, candidate_id, portal)
    
    if not account:
        account = PortalAccount(
            candidate_id=candidate_id,
            portal=portal,
            username=username,
            is_active=True,
        )
        db.add(account)
    
    # Check if account is locked
    if account.is_locked:
        logger.warning(
            "login_attempt_blocked_account_locked",
            candidate_id=candidate_id,
            portal=portal,
        )
        return {
            "status": LoginStatus.LOCKED,
            "reason": LoginFailureReason.ACCOUNT_LOCKED,
            "action": "operator_approval",
            "message": "Account is locked. Contact candidate.",
        }
    
    # Check rate limiting
    if account.login_attempts >= config.get("max_retries", 3):
        logger.warning(
            "login_rate_limited",
            candidate_id=candidate_id,
            portal=portal,
            attempts=account.login_attempts,
        )
        # Could implement rate limiting wait here
        pass
    
    # TODO: Actually perform login via browser/API
    # For now, simulate login attempt
    success = True  # Placeholder
    
    # Update account
    account.login_attempts += 1
    
    if success:
        account.is_active = True
        account.last_login = datetime.now().isoformat()
        account.login_attempts = 0
        # Session token would be set from actual login
        account.session_token = "simulated_session_token"
        
        await db.commit()
        
        logger.info(
            "login_success",
            candidate_id=candidate_id,
            portal=portal,
        )
        
        return {
            "status": LoginStatus.SUCCESS,
            "session_token": account.session_token,
        }
    else:
        await db.commit()
        
        logger.warning(
            "login_failed",
            candidate_id=candidate_id,
            portal=portal,
            attempts=account.login_attempts,
        )
        
        # Determine if should lock
        should_lock = account.login_attempts >= config.get("max_retries", 3)
        
        return {
            "status": LoginStatus.FAILED,
            "reason": LoginFailureReason.INVALID_CREDENTIALS,
            "attempts_remaining": config.get("max_retries", 3) - account.login_attempts,
            "should_lock": should_lock,
            "action": "retry" if not should_lock else "operator_approval",
        }


async def lock_portal_account(
    db: AsyncSession,
    candidate_id: str,
    portal: str,
    reason: str,
) -> PortalAccount:
    """Lock a portal account after repeated failures.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        portal: Portal name.
        reason: Reason for locking.
    
    Returns:
        Updated account.
    """
    account = await get_portal_account(db, candidate_id, portal)
    
    if account:
        account.is_locked = True
        account.notes = f"Locked: {reason}"
        await db.commit()
        await db.refresh(account)
        
        logger.warning(
            "portal_account_locked",
            candidate_id=candidate_id,
            portal=portal,
            reason=reason,
        )
    
    return account


async def unlock_portal_account(
    db: AsyncSession,
    candidate_id: str,
    portal: str,
) -> PortalAccount:
    """Unlock a portal account.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        portal: Portal name.
    
    Returns:
        Updated account.
    """
    account = await get_portal_account(db, candidate_id, portal)
    
    if account:
        account.is_locked = False
        account.login_attempts = 0
        account.notes = "Unlocked by system"
        await db.commit()
        await db.refresh(account)
        
        logger.info(
            "portal_account_unlocked",
            candidate_id=candidate_id,
            portal=portal,
        )
    
    return account


async def get_portal_health_score(
    db: AsyncSession,
    portal: str,
) -> dict[str, Any]:
    """Calculate portal health score.
    
    Based on:
    - Success rate
    - Average login time
    - Captcha/captcha rate
    
    Args:
        db: Database session.
        portal: Portal name.
    
    Returns:
        Health metrics.
    """
    result = await db.execute(
        select(PortalAccount).where(PortalAccount.portal == portal)
    )
    accounts = list(result.scalars().all())
    
    if not accounts:
        return {
            "portal": portal,
            "health_score": 0,
            "active_accounts": 0,
            "locked_accounts": 0,
        }
    
    active = sum(1 for a in accounts if a.is_active and not a.is_locked)
    locked = sum(1 for a in accounts if a.is_locked)
    total = len(accounts)
    
    # Simple health score
    health_score = (active / total * 100) if total > 0 else 0
    
    # Factor in locked accounts (negative)
    if locked > 0:
        health_score = health_score * (1 - (locked / total * 0.3))
    
    return {
        "portal": portal,
        "health_score": round(health_score, 2),
        "total_accounts": total,
        "active_accounts": active,
        "locked_accounts": locked,
        "average_login_attempts": sum(a.login_attempts for a in accounts) / total,
    }


async def handle_login_failure(
    db: AsyncSession,
    candidate_id: str,
    portal: str,
    failure_reason: str,
    attempts: int,
) -> dict[str, Any]:
    """Handle login failure - decide next action.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        portal: Portal name.
        failure_reason: Why login failed.
        attempts: Number of attempts.
    
    Returns:
        Action to take.
    """
    config = await get_login_config(portal)
    max_retries = config.get("max_retries", 3)
    
    if failure_reason == LoginFailureReason.ACCOUNT_LOCKED.value:
        return {
            "action": "escalate",
            "task_type": "login_fix",
            "message": "Account is locked",
            "instructions": f"Contact candidate to reset {portal} password",
        }
    
    if failure_reason in [
        LoginFailureReason.OTP_REQUIRED.value,
        LoginFailureReason.CAPTCHA_REQUIRED.value,
    ]:
        return {
            "action": "handle_exception",
            "exception_type": failure_reason.replace("_required", "_blocked"),
            "portal": portal,
        }
    
    if attempts >= max_retries:
        # Max retries reached - could escalate
        return {
            "action": "lock_and_escalate",
            "message": f"Max retries ({max_retries}) reached",
            "reason": "Too many failed attempts",
        }
    
    # Retry with wait
    return {
        "action": "retry",
        "wait_seconds": config.get("rate_limit_window", 60) * attempts,
    }


async def get_session_for_portal(
    db: AsyncSession,
    candidate_id: str,
    portal: str,
) -> str | None:
    """Get valid session token for portal.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        portal: Portal name.
    
    Returns:
        Session token if valid, None otherwise.
    """
    account = await get_portal_account(db, candidate_id, portal)
    
    if not account:
        return None
    
    # Check session validity
    if await check_session_valid(
        account.session_token,
        account.session_expires_at,
    ):
        return account.session_token
    
    return None
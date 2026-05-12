"""OTP Resolution Service - Auto-fetch and manage OTP verification.

Handles OTP verification flows per blueprint:
- Email OTP auto-fetch
- SMS integration logic  
- Candidate approval request
- Operator input if needed
- OTP expiry tracking
"""

from datetime import datetime, timedelta
from email import message_from_string
from enum import Enum
from typing import Any

import imaplib
import poplib
import structlog
import smtplib
from email.parser import Parser
from email.policy import default

from app.models.candidate import Candidate
from app.models.portal_account import PortalAccount

logger = structlog.get_logger(__name__)


class OTPType(str, Enum):
    """Types of OTP."""
    EMAIL = "email"
    SMS = "sms"
    AUTHENTICATOR = "authenticator"


class OTPStatus(str, Enum):
    """OTP resolution status."""
    REQUESTED = "requested"
    AUTO_FETCHED = "auto_fetched"
    MANUAL_ENTRY = "manual_entry"
    FAILED = "failed"
    EXPIRED = "expired"


class EmailProvider(str, Enum):
    """Supported email providers."""
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    YAHOO = "yahoo"
    IMAP = "imap"  # Generic IMAP


async def parse_imap_config(
    provider: str,
    email: str,
) -> dict[str, str]:
    """Get IMAP/SMTP configuration for email provider.
    
    Args:
        provider: Email provider name.
        email: Email address.
    
    Returns:
        Dict with host settings.
    """
    configs = {
        "gmail": {
            "imap_host": "imap.gmail.com",
            "imap_port": 993,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "use_ssl": True,
        },
        "outlook": {
            "imap_host": "outlook.office365.com",
            "imap_port": 993,
            "smtp_host": "smtp.office365.com",
            "smtp_port": 587,
            "use_ssl": True,
        },
        "yahoo": {
            "imap_host": "imap.mail.yahoo.com",
            "imap_port": 993,
            "smtp_host": "smtp.mail.yahoo.com",
            "smtp_port": 587,
            "use_ssl": True,
        },
    }
    
    provider_lower = provider.lower()
    if provider_lower in configs:
        return configs[provider_lower]
    
    # Default to Gmail-style
    return configs["gmail"]


async def fetch_email_otp(
    email: str,
    password: str,
    provider: str = "gmail",
    subject_keywords: list[str] = None,
    from_keywords: list[str] = None,
    timeout_seconds: int = 30,
) -> str | None:
    """Fetch OTP from email inbox.
    
    Attempts to find OTP in email by:
    1. Connecting to email provider via IMAP
    2. Searching for recent emails with OTP-related subjects
    3. Extracting numeric/code from email body
    
    Args:
        email: Email address.
        password: App password or OAuth token.
        provider: Email provider (gmail, outlook, yahoo, imap).
        subject_keywords: Keywords to search in subject.
        from_keywords: Keywords to search in sender.
        timeout_seconds: Max wait time.
    
    Returns:
        OTP code if found, None otherwise.
    """
    if subject_keywords is None:
        subject_keywords = ["verification", "code", "otp", "security code", "one-time"]
    
    if from_keywords is None:
        from_keywords = ["no-reply", "noreply", "verify", "security"]
    
    # Get provider config
    config = await parse_imap_config(provider, email)
    
    try:
        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(
            config["imap_host"], 
            config["imap_port"]
        )
        mail.login(email, password)
        
        # Select inbox
        status, _ = mail.select("INBOX")
        if status != "OK":
            logger.warning("imap_select_failed", email=email)
            return None
        
        # Search for recent emails
        import time
        cutoff = datetime.now() - timedelta(minutes=timeout_seconds)
        date_str = cutoff.strftime("%d-%b-%Y")
        
        # Build search query
        search_criteria = f'(SINCE "{date_str}")'
        status, messages = mail.search(None, search_criteria)
        
        if status != "OK":
            logger.warning("imap_search_failed", email=email)
            mail.logout()
            return None
        
        message_ids = messages[0].split()
        
        # Search backwards (newest first)
        for msg_id in reversed(message_ids[-10:]):
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            
            if status != "OK":
                continue
            
            msg_content = msg_data[0][1]
            email_msg = message_from_bytes(msg_content)
            
            # Check subject
            subject = email_msg.get("subject", "").lower()
            from_addr = email_msg.get("from", "").lower()
            
            # Filter by keywords
            subject_match = any(kw in subject for kw in subject_keywords)
            from_match = any(kw in from_addr for kw in from_keywords)
            
            if not (subject_match or from_match):
                continue
            
            # Get email body
            body = ""
            if email_msg.is_multipart():
                for part in email_msg.walk():
                    ctype = part.get_content_type()
                    cdispo = part.get("Content-Disposition")
                    
                    if ctype == "text/plain" and cdispo is None:
                        body = part.get_payload(decode=True)
                        if body:
                            body = body.decode("utf-8", errors="ignore")
                            break
            else:
                payload = email_msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
            
            # Extract OTP/code from body
            otp = extract_otp_from_text(body)
            if otp:
                mail.logout()
                logger.info(
                    "otp_fetched_from_email",
                    email=email,
                    subject=subject,
                )
                return otp
        
        mail.logout()
        logger.info("otp_not_found_in_email", email=email)
        return None
        
    except Exception as e:
        logger.error(
            "email_otp_fetch_error",
            email=email,
            error=str(e),
        )
        return None


def extract_otp_from_text(text: str) -> str | None:
    """Extract OTP/code from text.
    
    Looks for:
    - 6-digit codes
    - 8-digit codes
    - Alphanumeric codes
    
    Args:
        text: Text to search.
    
    Returns:
        Extracted code if found.
    """
    import re
    
    # 6-digit OTP (common)
    match = re.search(r"\b(\d{6})\b", text)
    if match:
        return match.group(1)
    
    # 8-digit code
    match = re.search(r"\b(\d{8})\b", text)
    if match:
        return match.group(1)
    
    # Alphanumeric code (6-8 chars, uppercase)
    match = re.search(r"\b([A-Z0-9]{6,8})\b", text)
    if match:
        return match.group(1)
    
    # "Your code is: XXXXXX" pattern
    match = re.search(r"(?:code|verification|otp)[:\s]*([A-Z0-9]{6,8})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


async def create_otp_request(
    candidate_id: str,
    portal: str,
    otp_type: str = "email",
    application_id: str | None = None,
) -> dict[str, Any]:
    """Create an OTP request record.
    
    Args:
        candidate_id: Candidate ID.
        portal: Portal requiring OTP.
        otp_type: Type of OTP.
        application_id: Related application.
    
    Returns:
        OTP request data.
    """
    return {
        "candidate_id": candidate_id,
        "portal": portal,
        "otp_type": otp_type,
        "application_id": application_id,
        "status": OTPStatus.REQUESTED,
        "requested_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(minutes=5),  # 5 min expiry
    }


async def validate_otp(
    otp_request: dict[str, Any],
    provided_otp: str,
) -> bool:
    """Validate provided OTP against request.
    
    Args:
        otp_request: OTP request data.
        provided_otp: OTP provided by user.
    
    Returns:
        True if valid.
    """
    # Check expiry
    if otp_request.get("expires_at"):
        if datetime.now() > otp_request["expires_at"]:
            logger.warning("otp_expired", candidate_id=otp_request.get("candidate_id"))
            return False
    
    # Check code
    stored_otp = otp_request.get("otp_code")
    if stored_otp and stored_otp == provided_otp:
        return True
    
    return False


async def handle_otp_failure(
    candidate_id: str,
    portal: str,
    failure_reason: str,
) -> dict[str, Any]:
    """Handle OTP failure - decide next action.
    
    Per blueprint:
    - If not found in email, request candidate/operator
    - If expired, retry request
    
    Args:
        candidate_id: Candidate ID.
        portal: Portal where OTP failed.
        reason: Why it failed.
    
    Returns:
        Action to take.
    """
    if failure_reason == "not_found":
        # Try SMS or authenticator as fallback
        return {
            "action": "request_fallback",
            "fallback_options": ["sms", "authenticator", "manual"],
            "request_candidate": True,
        }
    elif failure_reason == "expired":
        # Request new OTP
        return {
            "action": "retry",
            "retry_type": "new_request",
        }
    elif failure_reason == "wrong_code":
        # Try again or escalate
        return {
            "action": "retry_or_escalate",
            "attempts_remaining": 2,
        }
    
    # Default: escalate to operator
    return {
        "action": "escalate",
        "reason": failure_reason,
    }


# SMS OTP handling (placeholder for future integration)
async def send_sms_otp(
    phone_number: str,
    message: str,
    provider: str = "twilio",
) -> bool:
    """Send OTP via SMS.
    
    Note: Requires SMS provider integration (Twilio, etc.)
    
    Args:
        phone_number: Destination phone.
        message: Message to send.
        provider: SMS provider.
    
    Returns:
        True if sent successfully.
    """
    # Placeholder - would integrate with Twilio, AWS SNS, etc.
    logger.info(
        "sms_otp_placeholder",
        phone_number=phone_number[-4:],  # Only last 4 digits
        provider=provider,
    )
    return False


async def create_candidate_otp_approval_request(
    candidate_id: str,
    application_id: str,
    portal: str,
    otp_type: str,
) -> dict[str, Any]:
    """Create request for candidate to provide OTP manually.
    
    Used when auto-fetch fails.
    
    Args:
        candidate_id: Candidate ID.
        application_id: Application ID.
        portal: Portal needing OTP.
        otp_type: Type of OTP needed.
    
    Returns:
        Request data for candidate.
    """
    return {
        "type": "otp_approval",
        "candidate_id": candidate_id,
        "application_id": application_id,
        "portal": portal,
        "otp_type": otp_type,
        "instructions": f"Enter the {otp_type} verification code for {portal}",
        "expires_at": datetime.now() + timedelta(minutes=10),
    }
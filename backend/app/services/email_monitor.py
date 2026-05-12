"""Email Monitoring + Review Copilot.

Per blueprint:
- Monitors job-search inbox
- Classifies emails
- AI drafts replies
- Operator approves
- Status updates automatically
"""

from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EmailCategory(str, Enum):
    """Categories for incoming emails."""
    APPLICATION_CONFIRMATION = "application_confirmation"
    RECRUITER_REPLY = "recruiter_reply"
    INTERVIEW_REQUEST = "interview_request"
    REJECTION = "rejection"
    ASSESSMENT_LINK = "assessment_link"
    OTP = "otp"
    PORTAL_VERIFICATION = "portal_verification"
    UNKNOWN = "unknown"


class EmailPriority(str, Enum):
    """Email priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Email classification patterns
EMAIL_PATTERNS = {
    "application_confirmation": [
        "application received",
        "application submitted",
        "we received your application",
        "thank you for applying",
    ],
    "recruiter_reply": [
        "follow up",
        "wanted to reach out",
        "have you given more thought",
        "would like to discuss",
    ],
    "interview_request": [
        "invite",
        "would like to meet",
        "schedule a call",
        "interview",
        "next steps",
    ],
    "rejection": [
        "we've decided",
        "other candidates",
        "no longer considering",
        "gone in a different direction",
    ],
    "assessment_link": [
        "assessment",
        "take a test",
        "complete the evaluation",
    ],
    "portal_verification": [
        "verify your account",
        "confirm your email",
        "click here to verify",
    ],
}


async def classify_email(
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Classify an incoming email.
    
    Args:
        subject: Email subject.
        body: Email body.
    
    Returns:
        Classification data.
    """
    text = f"{subject} {body}".lower()
    
    for category, patterns in EMAIL_PATTERNS.items():
        for pattern in patterns:
            if pattern in text:
                priority = _get_priority_for_category(category)
                return {
                    "category": category,
                    "priority": priority,
                    "confidence": 0.9,
                    "action_needed": _get_action_for_category(category),
                }
    
    # Unknown
    return {
        "category": EmailCategory.UNKNOWN,
        "priority": EmailPriority.LOW,
        "confidence": 0.5,
        "action_needed": "review",
    }


def _get_priority_for_category(category: str) -> str:
    """Get priority for email category."""
    high = ["interview_request", "recruiter_reply", "assessment_link"]
    if category in high:
        return "high"
    medium = ["application_confirmation", "portal_verification"]
    if category in medium:
        return "medium"
    return "low"


def _get_action_for_category(category: str) -> str:
    """Get required action for category."""
    actions = {
        "application_confirmation": "track",
        "recruiter_reply": "respond",
        "interview_request": "escalate",
        "rejection": "track",
        "assessment_link": "notify_candidate",
        "portal_verification": "handle",
        "unknown": "review",
    }
    return actions.get(category, "review")


async def generate_reply_draft(
    email_category: str,
    context: dict[str, Any],
) -> str | None:
    """Generate AI reply draft for email.
    
    Per blueprint:
    - AI drafts reply
    - Operator approves
    - Status updates automatically
    
    Args:
        category: Email category.
        context: Context for the reply.
    
    Returns:
        Draft reply content or None.
    """
    candidate_name = context.get("candidate_name", "there")
    company = context.get("company", "your company")
    
    drafts = {
        "interview_request": f"""Hi,

Thank you so much for reaching out! I'd love to schedule a call. 
I'm available this week and next. Please let me know what times work best for you.

Looking forward to speaking with you!

{candidate_name}""",
        
        "recruiter_reply": f"""Hi,

Thank you for getting in touch! I'm still very interested in the position and would love to discuss any questions you might have.

Please let me know what works for you.

Best,
{candidate_name}""",
        
        "assessment_link": f"""Hi,

Thank you for the opportunity! I'll complete the assessment as soon as possible.

Please let me know if you have any questions.

Best,
{candidate_name}""",
    }
    
    return drafts.get(email_category)


async def process_email_for_application(
    application_id: str,
    email_category: str,
    email_content: dict[str, Any],
) -> dict[str, Any]:
    """Process incoming email and update application status.
    
    Args:
        application_id: Application ID.
        category: Email category.
        content: Email content.
    
    Returns:
        Action to take.
    """
    result = {
        "application_id": application_id,
        "category": email_category,
        "update_status": False,
        "new_status": None,
    }
    
    # Map category to status update
    status_map = {
        "interview_request": "interview_requested",
        "rejection": "rejected",
        "recruiter_reply": "response_received",
    }
    
    new_status = status_map.get(email_category)
    if new_status:
        result["update_status"] = True
        result["new_status"] = new_status
    
    # Also notify candidate for certain categories
    notify_categories = ["interview_request", "assessment_link"]
    result["notify_candidate"] = email_category in notify_categories
    
    logger.info(
        "email_processed",
        application_id=application_id,
        category=email_category,
        will_update_status=result["update_status"],
    )
    
    return result


async def get_unread_email_summary(
    emails: list[dict[str, Any]],
) -> dict[str, Any]:
    """Get summary of unread emails by category.
    
    Args:
        emails: List of email data.
    
    Returns:
        Category summary.
    """
    summary = {}
    
    for email in emails:
        category = email.get("category", "unknown")
        summary[category] = summary.get(category, 0) + 1
    
    return {
        "total_unread": len(emails),
        "by_category": summary,
        "high_priority": sum(1 for e in emails if e.get("priority") == "high"),
        "needs_review": sum(1 for e in emails if e.get("action_needed") == "review"),
    }


async def create_email_review_case(
    email_data: dict[str, Any],
    application_id: str | None = None,
) -> dict[str, Any]:
    """Create case for email needing human review.
    
    Args:
        email_data: Email classification data.
        application_id: Related application.
    
    Returns:
        Review case data.
    """
    case = {
        "type": "email_review",
        "email_subject": email_data.get("subject"),
        "email_category": email_data.get("category"),
        "priority": email_data.get("priority"),
        "application_id": application_id,
        "action": email_data.get("action_needed"),
        "created_at": datetime.now().isoformat(),
    }
    
    logger.info("email_review_case_created", **case)
    
    return case
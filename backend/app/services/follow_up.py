"""Follow-Up Engine - Automated follow-up sequences.

Per blueprint:
- No response after 3 days → follow-up 1
- No response after 7 days → follow-up 2
- Reply received → stop sequence
- Rejected → stop sequence
- Interview request → status update

Tracks:
- Sent follow-ups
- Response rate
- Portal/source performance
- Candidate-level follow-up history
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application

logger = structlog.get_logger(__name__)


class FollowUpStatus(str, Enum):
    """Follow-up sequence status."""
    PENDING = "pending"
    SENT = "sent"
    RESPONSE_RECEIVED = "response_received"
    INTERVIEW_REQUESTED = "interview_requested"
    REJECTED = "rejected"
    STOPPED = "stopped"


class FollowUpTemplate(str, Enum):
    """Follow-up templates."""
    FIRST = "first"      # 3 days
    SECOND = "second"    # 7 days
    FINAL = "final"     # 14 days (optional)


# Follow-up timing (per blueprint)
FOLLOW_UP_TIMING = {
    "first": 3,    # days after submitted
    "second": 7,   # days after first follow-up
    "final": 14,   # days after second follow-up
}


# Follow-up message templates
FOLLOW_UP_MESSAGES = {
    "first": """Subject: Following up on my application for {job_title}

Hi {recruiter_name or 'there'},

I wanted to follow up on my application for the {job_title} position at {company}. 
I'm still very interested in this opportunity and would love to discuss how I can contribute to your team.

Please let me know if you need any additional information.

Best regards,
{candidate_name}""",
    
    "second": """Subject: Check-in: {job_title} Application

Hi {recruiter_name or 'there'},

I wanted to check in again on my application for the {job_title} role. 
I understand things get busy, but I'm very excited about the possibility of joining {company}.

Please let me know if there's anything I can do to move the process forward.

Best,
{candidate_name}""",
    
    "final": """Subject: Final check-in: {job_title}

Hi {recruiter_name or 'there'},

I wanted to reach out one last time regarding my application for {job_title}. 
I remain very interested, but I don't want to take up any more of your time if the position has been filled.

If there's still interest, I'd be happy to chat. Otherwise, I wish you and the team the best!

{candidate_name}""",
}


async def should_send_follow_up(
    application: Application,
    follow_up_count: int,
) -> bool:
    """Determine if follow-up should be sent.
    
    Rules:
    - No response after 3 days → follow-up 1
    - No response after 7 days → follow-up 2
    - Reply received → stop
    - Rejected → stop
    
    Args:
        application: Application to check.
        follow_up_count: Current follow-up count.
    
    Returns:
        True if should follow up.
    """
    # Don't follow up if not submitted
    if application.status != "submitted":
        return False
    
    # Stop if rejected/received response
    if application.status in ["rejected", "response_received", "interview_requested"]:
        return False
    
    # Check timing
    if not application.applied_at:
        return False
    
    days_since_apply = (datetime.now() - application.applied_at).days
    
    if follow_up_count == 0 and days_since_apply >= FOLLOW_UP_TIMING["first"]:
        return True
    if follow_up_count == 1 and days_since_apply >= FOLLOW_UP_TIMING["second"]:
        return True
    if follow_up_count >= 2:
        return False
    
    return False


async def get_follow_up_sequence(
    application: Application,
    follow_up_count: int,
) -> dict[str, Any]:
    """Get the appropriate follow-up for the sequence position.
    
    Args:
        application: Application.
        follow_up_count: Current count.
    
    Returns:
        Follow-up data.
    """
    if follow_up_count == 0:
        template = FollowUpTemplate.FIRST
    elif follow_up_count == 1:
        template = FollowUpTemplate.SECOND
    else:
        template = FollowUpTemplate.FINAL
    
    return {
        "template": template.value,
        "timing_days": FOLLOW_UP_TIMING[template.value],
        "message": FOLLOW_UP_MESSAGES[template.value],
    }


async def record_follow_up_sent(
    db: AsyncSession,
    application_id: str,
    follow_up_number: int,
    response_status: str = "sent",
) -> Application:
    """Record a follow-up being sent.
    
    Args:
        db: Database session.
        application_id: Application ID.
        follow_up_number: Which follow-up (1, 2, 3).
        response_status: Status after sending.
    
    Returns:
        Updated application.
    """
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    
    if app:
        app.follow_up_count = follow_up_number
        app.last_follow_up_at = datetime.now()
        
        # Set next follow-up timing
        next_timing = FOLLOW_UP_TIMING.get(
            FollowUpTemplate(follow_up_number + 1).value,
            7
        )
        app.next_follow_up_at = datetime.now() + timedelta(days=next_timing)
        
        await db.commit()
        await db.refresh(app)
        
        logger.info(
            "follow_up_recorded",
            application_id=application_id,
            follow_up_number=follow_up_number,
        )
    
    return app


async def handle_application_response(
    db: AsyncSession,
    application_id: str,
    response_type: str,
) -> Application:
    """Handle application response - stop follow-up sequence.
    
    Args:
        db: Database session.
        application_id: Application ID.
        response_type: Type of response (response_received, interview_requested, rejected).
    
    Returns:
        Updated application.
    """
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    
    if app:
        # Update status based on response
        if response_type == "interview_requested":
            app.status = "interview_requested"
        elif response_type == "rejected":
            app.status = "rejected"
        elif response_type == "response_received":
            app.status = "response_received"
        
        # Clear follow-up schedule
        app.next_follow_up_at = None
        
        await db.commit()
        await db.refresh(app)
        
        logger.info(
            "response_received",
            application_id=application_id,
            response_type=response_type,
        )
    
    return app


async def get_follow_up_queue(
    db: AsyncSession,
    days_window: int = 1,
) -> list[Application]:
    """Get applications needing follow-up.
    
    Args:
        db: Database session.
        days_window: How far ahead to look.
    
    Returns:
        Applications due for follow-up.
    """
    now = datetime.now()
    cutoff = now + timedelta(days=days_window)
    
    query = select(Application).where(
        Application.status == "submitted",
        Application.next_follow_up_at <= cutoff,
        Application.next_follow_up_at >= now,
    )
    
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_follow_up_stats(
    db: AsyncSession,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    """Get follow-up statistics.
    
    Args:
        db: Database session.
        candidate_id: Optional candidate filter.
    
    Returns:
        Follow-up stats.
    """
    query = select(Application)
    
    if candidate_id:
        query = query.where(Application.candidate_id == candidate_id)
    
    result = await db.execute(query)
    apps = list(result.scalars().all())
    
    total_follow_ups = sum(app.follow_up_count for app in apps if app.follow_up_count)
    responses = sum(1 for app in apps if app.status == "response_received")
    interviews = sum(1 for app in apps if app.status == "interview_requested")
    rejected = sum(1 for app in apps if app.status == "rejected")
    
    return {
        "total_applications": len(apps),
        "total_follow_ups_sent": total_follow_ups,
        "responses_received": responses,
        "interview_requests": interviews,
        "rejections": rejected,
        "response_rate": responses / len(apps) if apps else 0,
        "interview_rate": interviews / len(apps) if apps else 0,
        "follow_up_response_rate": responses / total_follow_ups if total_follow_ups else 0,
    }


async def generate_follow_up_email(
    application: Application,
    job_data: dict[str, Any],
    candidate_data: dict[str, Any],
    follow_up_number: int,
) -> str:
    """Generate personalized follow-up email.
    
    Args:
        application: Application.
        job_data: Job info.
        candidate_data: Candidate info.
        follow_up_number: Which follow-up.
    
    Returns:
        Generated email content.
    """
    template = await get_follow_up_sequence(application, follow_up_number)
    message = template["message"]
    
    # Fill in variables
    variables = {
        "job_title": job_data.get("title", "Position"),
        "company": job_data.get("company", "Company"),
        "recruiter_name": job_data.get("recruiter_name", ""),
        "candidate_name": f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}",
    }
    
    return message.format(**variables)
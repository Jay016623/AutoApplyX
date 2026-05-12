"""KPI + Analytics Command Center.

Per blueprint:
- Applications/day
- Applications/candidate
- Jobs discovered
- Jobs matched
- Jobs skipped
- Follow-ups sent
- Responses received
- Interview requests
- Portal success rate
- Captcha rate
- OTP success rate
- Human touch percentage
- Automation percentage
- Average resolution time
- Operator productivity
- Resume performance
- Candidate performance
"""

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.daily_metric import DailyMetric
from app.models.job import Job
from app.models.exception_case import ExceptionCase

logger = structlog.get_logger(__name__)


async def get_dashboard_kpis(
    db: AsyncSession,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Get comprehensive KPI dashboard data.
    
    Args:
        db: Database session.
        date_from: Start date (YYYY-MM-DD).
        date_to: End date (YYYY-MM-DD).
    
    Returns:
        Dashboard KPI data.
    """
    # Applications
    app_result = await db.execute(select(Application))
    apps = list(app_result.scalars().all())
    
    submitted = [a for a in apps if a.status == "submitted"]
    rejected = [a for a in apps if a.status == "rejected"]
    responses = [a for a in apps if a.status in ["response_received", "interview_requested"]]
    
    # Jobs
    job_result = await db.execute(select(Job))
    jobs = list(job_result.scalars().all())
    
    matched = [j for j in jobs if j.match_score and j.match_score >= 70]
    skipped = [j for j in jobs if j.match_score and j.match_score < 55]
    
    # Candidates
    cand_result = await db.execute(select(Candidate).where(Candidate.status == "active"))
    active_candidates = list(cand_result.scalars().all())
    
    # Exceptions
    exc_result = await db.execute(select(ExceptionCase))
    exceptions = list(exc_result.scalars().all())
    
    resolved_human = [e for e in exceptions if e.status in ["resolved_permanent", "operator_in_progress"]]
    
    return {
        "applications": {
            "total": len(apps),
            "submitted": len(submitted),
            "rejected": len(rejected),
            "response_rate": len(responses) / len(submitted) if submitted else 0,
            "interview_rate": sum(1 for a in submitted if a.status == "interview_requested") / len(submitted) if submitted else 0,
            "per_day": _calculate_applications_per_day(submitted),
        },
        "jobs": {
            "total": len(jobs),
            "discovered_today": len([j for j in jobs if j.created_at.date() == datetime.now().date()]),
            "matched": len(matched),
            "skipped": len(skipped),
        },
        "candidates": {
            "active": len(active_candidates),
            "applications_per_candidate": len(submitted) / len(active_candidates) if active_candidates else 0,
        },
        "exceptions": {
            "total": len(exceptions),
            "resolved_human": len(resolved_human),
            "resolution_rate": len([e for e in exceptions if e.status.startswith("resolved")]) / len(exceptions) if exceptions else 0,
        },
        "automation": {
            "human_touch_percentage": (len(resolved_human) / len(exceptions) * 100 if exceptions else 0),
            "automation_percentage": (100 - (len(resolved_human) / len(exceptions) * 100 if exceptions else 0)),
        },
    }


async def get_portal_performance(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Get performance metrics by portal.
    
    Returns:
        Portal performance data.
    """
    result = await db.execute(select(Application).where(Application.portal.isnot(None)))
    apps = list(result.scalars().all())
    
    # Group by portal
    portal_data = {}
    for app in apps:
        portal = app.portal or "unknown"
        if portal not in portal_data:
            portal_data[portal] = {
                "portal": portal,
                "total": 0,
                "submitted": 0,
                "responses": 0,
                "interviews": 0,
            }
        
        portal_data[portal]["total"] += 1
        if app.status == "submitted":
            portal_data[portal]["submitted"] += 1
        if app.status in ["response_received", "interview_requested"]:
            portal_data[portal]["responses"] += 1
        if app.status == "interview_requested":
            portal_data[portal]["interviews"] += 1
    
    # Calculate rates
    for portal, data in portal_data.items():
        if data["submitted"]:
            data["response_rate"] = data["responses"] / data["submitted"]
            data["interview_rate"] = data["interviews"] / data["submitted"]
    
    return list(portal_data.values())


async def get_candidate_leaderboard(
    db: AsyncSession,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get top performing candidates.
    
    Args:
        db: Database session.
        limit: Number to return.
    
    Returns:
        Candidate performance.
    """
    result = await db.execute(select(Candidate).where(Candidate.status == "active"))
    candidates = list(result.scalars().all())
    
    # Get applications for each candidate
    leaderboard = []
    for cand in candidates:
        app_result = await db.execute(
            select(Application).where(Application.candidate_id == cand.id)
        )
        cand_apps = list(app_result.scalars().all())
        
        submitted = [a for a in cand_apps if a.status == "submitted"]
        interviews = sum(1 for a in cand_apps if a.status == "interview_requested")
        
        leaderboard.append({
            "candidate_id": cand.id,
            "name": f"{cand.first_name} {cand.last_name}",
            "target_role": cand.target_role,
            "applications": len(submitted),
            "interviews": interviews,
            "interview_rate": interviews / len(submitted) if submitted else 0,
        })
    
    # Sort by interviews
    leaderboard.sort(key=lambda x: (x["interviews"], x["applications"]), reverse=True)
    
    return leaderboard[:limit]


def _calculate_applications_per_day(applications: list[Application]) -> float:
    """Calculate average applications per day."""
    if not applications:
        return 0
    
    dates = [a.applied_at.date() for a in applications if a.applied_at]
    if not dates:
        return 0
    
    min_date = min(dates)
    max_date = max(dates)
    days = (max_date - min_date).days or 1
    
    return len(applications) / days


async def get_daily_summary(
    db: AsyncSession,
    date: str | None = None,
) -> dict[str, Any]:
    """Get daily summary for a specific date.
    
    Args:
        db: Database session.
        date: Date string (YYYY-MM-DD). Defaults to today.
    
    Returns:
        Daily summary.
    """
    target_date = datetime.now().date()
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    
    # Get today's applications
    result = await db.execute(select(Application))
    all_apps = list(result.scalars().all())
    
    today_apps = [
        a for a in all_apps
        if a.applied_at and a.applied_at.date() == target_date
    ]
    
    submitted = [a for a in today_apps if a.status == "submitted"]
    responses = [a for a in today_apps if a.status in ["response_received", "interview_requested"]]
    
    return {
        "date": target_date.isoformat(),
        "applications_submitted": len(submitted),
        "responses": len(responses),
        "interviews": sum(1 for a in today_apps if a.status == "interview_requested"),
        "rejections": sum(1 for a in today_apps if a.status == "rejected"),
    }


async def get_operator_productivity(
    db: AsyncSession,
) -> dict[str, Any]:
    """Get operator productivity metrics."""
    from app.models.operator_task import OperatorTask
    
    result = await db.execute(select(OperatorTask))
    tasks = list(result.scalars().all())
    
    completed = [t for t in tasks if t.status == "completed"]
    pending = [t for t in tasks if t.status == "pending"]
    in_progress = [t for t in tasks if t.status == "in_progress"]
    
    return {
        "total_tasks": len(tasks),
        "completed": len(completed),
        "pending": len(pending),
        "in_progress": len(in_progress),
        "completion_rate": len(completed) / len(tasks) if tasks else 0,
    }


async def get_resume_performance(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Get resume performance metrics."""
    from app.models.resume import Resume
    
    result = await db.execute(select(Resume))
    resumes = list(result.scalars().all())
    
    performance = []
    for resume in resumes:
        app_result = await db.execute(
            select(Application).where(Application.resume_id == resume.id)
        )
        apps = list(app_result.scalars().all())
        
        submitted = [a for a in apps if a.status == "submitted"]
        interviews = sum(1 for a in apps if a.status == "interview_requested")
        
        performance.append({
            "resume_id": resume.id,
            "name": resume.name,
            "type": resume.type,
            "applications": len(submitted),
            "interviews": interviews,
            "ats_score": resume.ats_score,
        })
    
    return performance
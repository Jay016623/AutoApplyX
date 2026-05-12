"""Resume Tailoring Engine - JD-based resume customization.

Per blueprint:
- Resume parsing
- Master resume storage
- Role-specific resume versions
- JD-based tailoring
- Cover letter generation
- ATS keyword alignment
- Fallback resume selection
- Resume performance tracking
"""

from datetime import datetime
from enum import Enum
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.job import Job
from app.models.resume import Resume

logger = structlog.get_logger(__name__)


class TailoringStrategy(str, Enum):
    """Resume tailoring strategies."""
    EXACT_MATCH = "exact_match"     # Perfect skill match
    KEYWORD_DENSITY = "keyword_density"  # High keyword overlap
    ATS_OPTIMIZED = "ats_optimized"  # ATS-focused rewrite
    MINIMAL = "minimal"           # Basic modifications


async def select_best_resume(
    db: AsyncSession,
    candidate: Candidate,
    job: Job,
) -> Resume | None:
    """Select the best resume for a job.
    
    Per blueprint:
    1. Check for role-specific version
    2. Check for job-specific tailored version
    3. Use base master resume
    4. Fallback to primary resume
    
    Args:
        db: Database session.
        candidate: Candidate.
        job: Job to apply to.
    
    Returns:
        Best resume to use.
    """
    # Get all resumes for candidate
    result = await db.execute(
        select(Resume)
        .where(Resume.job_id == job.id)
        .order_by(Resume.created_at.desc())
    )
    job_resumes = list(result.scalars().all())
    
    # Check for tailored version (prefer)
    for resume in job_resumes:
        if resume.type == "tailored":
            logger.info("selected_tailored_resume", resume_id=resume.id, job_id=job.id)
            return resume
    
    # Get role-specific resume (same target role)
    if candidate.target_role:
        result = await db.execute(
            select(Resume)
            .where(Resume.name.contains(candidate.target_role))
            .order_by(Resume.created_at.desc())
        )
        role_resumes = list(result.scalars().all())
        if role_resumes:
            logger.info("selected_role_resume", resume_id=role_resumes[0].id)
            return role_resumes[0]
    
    # Fallback to primary resume
    if candidate.primary_resume_id:
        result = await db.execute(
            select(Resume).where(Resume.id == candidate.primary_resume_id)
        )
        primary = result.scalar_one_or_none()
        if primary:
            logger.info("selected_primary_resume", resume_id=primary.id)
            return primary
    
    # Fallback to any base resume
    result = await db.execute(
        select(Resume)
        .where(Resume.type == "base")
        .order_by(Resume.created_at.desc())
    )
    base = result.scalar_one_or_none()
    
    if base:
        logger.info("selected_base_resume", resume_id=base.id)
    
    return base


async def tailor_resume_for_job(
    db: AsyncSession,
    base_resume_id: str,
    job_id: str,
    strategy: str = "ats_optimized",
) -> Resume:
    """Tailor a resume for a specific job.
    
    Args:
        db: Database session.
        base_resume_id: Base resume to tailor.
        job_id: Target job.
        strategy: Tailoring strategy.
    
    Returns:
        Tailored resume.
    """
    # Get base resume and job
    result = await db.execute(
        select(Resume).where(Resume.id == base_resume_id)
    )
    base_resume = result.scalar_one_or_none()
    
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not base_resume or not job:
        raise ValueError(f"Resume {base_resume_id} or Job {job_id} not found")
    
    # Build tailored content
    tailored_content = await _build_tailored_content(
        base_resume.content_text or "",
        job.description,
        strategy,
    )
    
    # Create tailored resume
    tailored_resume = Resume(
        name=f"Tailored - {job.title} at {job.company}",
        type="tailored",
        template_id=base_resume.template_id,
        base_resume_id=base_resume_id,
        job_id=job_id,
        content_text=tailored_content,
    )
    
    db.add(tailored_resume)
    await db.commit()
    await db.refresh(tailored_resume)
    
    logger.info(
        "resume_tailored",
        base_id=base_resume_id,
        tailored_id=tailored_resume.id,
        job_id=job_id,
    )
    
    return tailored_resume


async def _build_tailored_content(
    resume_text: str,
    job_description: str,
    strategy: str,
) -> str:
    """Build tailored resume content based on JD.
    
    Uses LLM to rewrite resume content to better match job description.
    This is a simplified version - full version would use LLM.
    """
    # Extract keywords from JD
    job_keywords = _extract_keywords(job_description)
    
    # Simple keyword injection (placeholder for LLM-based rewrite)
    tailored = resume_text
    
    # In production, this would call LLM to:
    # 1. Identify relevant experiences
    # 2. Rephrase for JD alignment
    # 3. Add missing keywords naturally
    
    logger.info(
        "resume_content_tailored",
        original_length=len(resume_text),
        new_length=len(tailored),
        job_keywords=len(job_keywords),
    )
    
    return tailored


def _extract_keywords(text: str) -> list[str]:
    """Extract ATS keywords from job description."""
    import re
    
    # Common tech keywords
    keywords = [
        "python", "java", "javascript", "sql", "aws", "docker", "kubernetes",
        "react", "angular", "vue", "node", "django", "flask", "fastapi",
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "git", "jenkins", "ci/cd", "agile", "scrum",
        "machine learning", "data science", "deep learning",
        "rest api", "graphql", "microservices",
        "linux", "bash", "shell",
    ]
    
    text_lower = text.lower()
    found = [kw for kw in keywords if kw in text_lower]
    
    # Also extract capitalized phrases
    phrases = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', text)
    found.extend([p for p in phrases if len(p) > 3][:10])
    
    return found


async def align_ats_keywords(
    resume_text: str,
    job_description: str,
    ats_score: float | None = None,
) -> dict[str, Any]:
    """Align resume with ATS keywords from job description.
    
    Args:
        resume_text: Resume content.
        job_description: Job description.
        ats_score: Existing ATS score.
    
    Returns:
        Keyword alignment report.
    """
    job_keywords = _extract_keywords(job_description)
    resume_keywords = _extract_keywords(resume_text)
    
    # Calculate alignment
    job_set = set(kw.lower() for kw in job_keywords)
    resume_set = set(kw.lower() for kw in resume_keywords)
    
    matched = job_set & resume_set
    missing = job_set - resume_set
    
    # Density score
    density = len(matched) / len(job_set) if job_set else 0
    
    return {
        "job_keywords": job_keywords,
        "resume_keywords": resume_keywords,
        "matched_count": len(matched),
        "missing_count": len(missing),
        "density_score": round(density, 3),
        "missing_keywords": list(missing),
        "ats_score": ats_score,
    }


async def track_resume_performance(
    db: AsyncSession,
    resume_id: str,
    application_id: str,
    result: str,
) -> dict[str, Any]:
    """Track resume performance for analytics.
    
    Args:
        db: Database session.
        resume_id: Resume ID.
        application_id: Application ID.
        result: Result (submitted, viewed, interview, rejected).
    
    Returns:
        Tracking record.
    """
    record = {
        "resume_id": resume_id,
        "application_id": application_id,
        "result": result,
        "tracked_at": datetime.now().isoformat(),
    }
    
    logger.info("resume_performance_tracked", **record)
    
    return record


async def get_resume_performance_summary(
    db: AsyncSession,
    resume_id: str,
) -> dict[str, Any]:
    """Get performance summary for a resume.
    
    Args:
        db: Database session.
        resume_id: Resume ID.
    
    Returns:
        Performance metrics.
    """
    # This would query applications for this resume
    return {
        "resume_id": resume_id,
        "total_applications": 0,
        "viewed_count": 0,
        "interview_count": 0,
        "rejection_count": 0,
        "view_rate": 0.0,
        "interview_rate": 0.0,
    }
"""AI Match Brain - Candidate-Job Scoring Service.

Scores candidate-job fit across multiple dimensions:
- Skill fit (required skills match)
- Title fit (job title match)
- Experience fit (years of experience)
- Location fit (location preferences)
- Salary fit (salary expectations)
- Visa fit (work authorization)

Decision thresholds per blueprint:
- 85+ score = apply immediately
- 70-84 = apply if target volume not filled
- 55-69 = hold
- Below 55 = skip
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.candidate import Candidate
from app.models.job import Job
from app.models.application import Application, APPLICATION_STATES

logger = structlog.get_logger(__name__)


# Scoring constants
SCORE_IMMEDIATE_APPLY = 85  # Apply immediately
SCORE_VOLUME_APPLY = 70     # Apply if target volume not filled
SCORE_HOLD = 55            # Hold for review
SCORE_SKIP = 0             # Skip entirely

# Weights for overall score calculation (must sum to 1.0)
WEIGHTS = {
    "skill": 0.30,        # 30% - Skills are most important
    "title": 0.20,        # 20% - Title match matters
    "experience": 0.15,    # 15% - Experience alignment
    "location": 0.15,     # 15% - Location preference
    "salary": 0.10,       # 10% - Salary fit
    "visa": 0.10,        # 10% - Work authorization
}


@dataclass
class MatchScores:
    """Individual match scores for a candidate-job pair."""
    skill_score: float | None = None
    title_score: float | None = None
    experience_score: float | None = None
    location_score: float | None = None
    salary_score: float | None = None
    visa_score: float | None = None
    overall_score: float | None = None
    interview_probability: float | None = None
    recommendation: str | None = None


@dataclass
class AllocationCandidate:
    """Candidate with allocation priority info."""
    candidate_id: str
    overall_score: float
    interview_probability: float
    applications_today: int
    daily_apply_limit: int
    applications_to_same_company: int


async def calculate_skill_score(candidate: Candidate, job: Job) -> float | None:
    """Calculate skill match score (0-100).
    
    Compares candidate's skill confidence matrix with job's required skills.
    """
    if not candidate.skill_confidence or not job.skills_required:
        return None
    
    candidate_skills = candidate.skill_confidence
    required_skills = job.skills_required
    
    if not required_skills:
        return None
    
    total_weight = 0.0
    matched_weight = 0.0
    
    # Check each required skill
    for skill, weight in required_skills.items():
        total_weight += weight
        skill_key = skill.lower()
        
        # Check exact match first
        if skill_key in candidate_skills:
            confidence = candidate_skills[skill_key]
            # Scale confidence (1-5) to score (20-100)
            matched_weight += weight * (confidence * 20)
        else:
            # Check partial matches (e.g., "python" in "python django")
            for cand_skill, confidence in candidate_skills.items():
                if skill_key in cand_skill or cand_skill in skill_key:
                    matched_weight += weight * (confidence * 20)
                    break
    
    if total_weight == 0:
        return None
    
    return min(100.0, (matched_weight / total_weight) * 100)


async def calculate_title_score(candidate: Candidate, job: Job) -> float | None:
    """Calculate job title match score (0-100).
    
    Compares candidate's target roles with job title.
    """
    target_roles = [
        candidate.target_role,
        candidate.target_role_2,
        candidate.target_role_3,
    ]
    target_roles = [r.lower() for r in target_roles if r]
    
    if not target_roles:
        return None
    
    job_title = job.title.lower()
    
    # Check for exact or close match
    for role in target_roles:
        if role in job_title or job_title in role:
            return 100.0
        
        # Check partial word matches (80% if key words match)
        role_words = set(role.split())
        title_words = set(job_title.split())
        overlap = len(role_words & title_words)
        
        if overlap > 0 and overlap >= min(len(role_words), len(title_words)) * 0.5:
            return 80.0
    
    return 25.0  # No apparent match


async def calculate_experience_score(candidate: Candidate, job: Job) -> float | None:
    """Calculate experience match score (0-100).
    
    Compares candidate's years of experience with job requirements.
    """
    if not candidate.years_experience or not job.experience_level:
        return None
    
    try:
        cand_years = int(candidate.years_experience)
    except (ValueError, TypeError):
        return None
    
    # Parse job experience level
    exp_level = job.experience_level.lower()
    
    if "entry" in exp_level or "junior" in exp_level or "0-2" in exp_level:
        min_exp, max_exp = 0, 2
    elif "mid" in exp_level or "associate" in exp_level or "2-4" in exp_level:
        min_exp, max_exp = 2, 4
    elif "senior" in exp_level or "5+" in exp_level or "5-7" in exp_level:
        min_exp, max_exp = 5, 10
    elif "principal" in exp_level or "director" in exp_level or "10+" in exp_level:
        min_exp, max_exp = 10, 20
    else:
        return None  # Can't determine
    
    # Calculate score
    if min_exp <= cand_years <= max_exp:
        return 100.0
    elif cand_years < min_exp:
        # Under-qualified
        return max(0.0, 100.0 - (min_exp - cand_years) * 20)
    else:
        # Over-qualified (slight penalty)
        return max(60.0, 100.0 - (cand_years - max_exp) * 5)


async def calculate_location_score(candidate: Candidate, job: Job) -> float | None:
    """Calculate location preference match score (0-100).
    
    Compares candidate's preferred locations with job location.
    """
    if not candidate.preferred_locations:
        return None
    
    # Parse stored JSON locations
    try:
        import json
        preferred = json.loads(candidate.preferred_locations)
    except (json.JSONDecodeError, TypeError):
        preferred = [candidate.preferred_locations]
    
    if not preferred:
        return None
    
    job_location = job.location.lower()
    job_remote = job.remote
    
    for loc in preferred:
        loc_lower = loc.lower()
        
        # Exact location match
        if loc_lower == job_location:
            return 100.0
        
        # City match (e.g., "New York" in "New York, NY")
        if loc_lower in job_location or job_location in loc_lower:
            return 90.0
        
        # Remote match
        if "remote" in loc_lower and job_remote:
            return 100.0
        if "remote" in loc_lower and not job_remote:
            return 50.0  # Prefers remote but job is onsite
        
        # State match
        if "," in loc_lower:
            state = loc_lower.split(",")[-1].strip()
            if state in job_location:
                return 80.0
    
    return 25.0  # No match


async def calculate_salary_score(candidate: Candidate, job: Job) -> float | None:
    """Calculate salary fit score (0-100).
    
    Compares candidate's salary expectations with job's salary range.
    """
    if not candidate.salary_min and not candidate.salary_max:
        return None
    
    if not job.salary_range:
        return None
    
    # Parse job salary range (e.g., "$100k - $150k")
    import re
    salary_match = re.findall(r"\d+", job.salary_range.replace(",", ""))
    
    if not salary_match:
        return None
    
    try:
        job_salary_min = int(salary_match[0]) * 1000  # Convert k to actual
        job_salary_max = int(salary_match[-1]) * 1000
    except (ValueError, IndexError):
        return None
    
    # Candidate expectations
    cand_min = int(candidate.salary_min) if candidate.salary_min else 0
    cand_max = int(candidate.salary_max) if candidate.salary_max else 999999
    
    # Calculate overlap
    if cand_max < job_salary_min:
        return 0.0  # Candidate wants more than offered
    elif cand_min > job_salary_max:
        return 0.0  # Candidate wants less than offered (unlikely to apply)
    else:
        # Good overlap
        overlap_start = max(cand_min, job_salary_min)
        overlap_end = min(cand_max, job_salary_max)
        overlap = overlap_end - overlap_start
        
        cand_range = cand_max - cand_min if cand_max > cand_min else 1
        job_range = job_salary_max - job_salary_min if job_salary_max > job_salary_min else 1
        
        return min(100.0, (overlap / max(cand_range, job_range)) * 100)


async def calculate_visa_score(candidate: Candidate, job: Job) -> float | None:
    """Calculate visa/work authorization fit score (0-100).
    
    Checks if candidate's visa status matches job requirements.
    """
    if not candidate.visa_status:
        return 50.0  # Unknown - neutral score
    
    visa = candidate.visa_status.lower()
    
    # Check job description for visa hints
    desc = job.description.lower()
    
    # Strong sponsorship signals in job
    if "must require sponsorship" in desc or "requires sponsorship" in desc:
        if candidate.needs_sponsorship:
            return 100.0  # Both need sponsorship
        else:
            return 50.0  # Job needs, candidate has
    
    # No sponsorship mentioned
    if "uscis" not in desc and "sponsor" not in desc:
        # Any status works
        if visa in ("us_citizen", "green_card"):
            return 100.0
        elif visa in ("h1b", "l1", "opt", "cpt"):
            return 80.0  # Work authorized
        else:
            return 50.0
    
    # Sponsorship required but unclear
    return 50.0


def calculate_interview_probability(scores: MatchScores) -> float:
    """Calculate predicted interview probability based on scores.
    
    Based on historical patterns - higher scores correlate with more interviews.
    """
    if not scores.overall_score:
        return 0.0
    
    # Base probability from overall score
    base = scores.overall_score * 0.5  # Max 50% from score
    
    # Bonus for strong skills (most predictive)
    skill_bonus = (scores.skill_score or 0) * 0.2
    
    # Bonus for title match
    title_bonus = (scores.title_score or 0) * 0.15
    
    # Bonus for visa eligibility
    visa_bonus = (scores.visa_score or 0) * 0.1
    
    # Penalty for location mismatch
    location_penalty = max(0, (scores.location_score or 50) - 50) * 0.1
    
    probability = base + skill_bonus + title_bonus + visa_bonus - location_penalty
    
    return min(95.0, max(5.0, probability))


def get_recommendation(overall_score: float) -> str:
    """Get application recommendation based on overall score.
    
    Per blueprint:
    - 85+ = apply immediately
    - 70-84 = apply if target volume not filled
    - 55-69 = hold
    - Below 55 = skip
    """
    if overall_score >= SCORE_IMMEDIATE_APPLY:
        return "apply_immediate"
    elif overall_score >= SCORE_VOLUME_APPLY:
        return "apply_if_volume"
    elif overall_score >= SCORE_HOLD:
        return "hold"
    else:
        return "skip"


async def score_candidate_job(
    db: AsyncSession,
    candidate: Candidate,
    job: Job,
) -> MatchScores:
    """Calculate all match scores for a candidate-job pair.
    
    Args:
        db: Database session.
        candidate: Candidate to score.
        job: Job to score against.
    
    Returns:
        MatchScores with all individual scores and overall recommendation.
    """
    # Calculate individual scores
    skill_score = await calculate_skill_score(candidate, job)
    title_score = await calculate_title_score(candidate, job)
    experience_score = await calculate_experience_score(candidate, job)
    location_score = await calculate_location_score(candidate, job)
    salary_score = await calculate_salary_score(candidate, job)
    visa_score = await calculate_visa_score(candidate, job)
    
    # Calculate weighted overall score
    scores = MatchScores(
        skill_score=skill_score,
        title_score=title_score,
        experience_score=experience_score,
        location_score=location_score,
        salary_score=salary_score,
        visa_score=visa_score,
    )
    
    # Calculate weighted overall
    weighted_sum = 0.0
    weight_total = 0.0
    
    if skill_score is not None:
        weighted_sum += skill_score * WEIGHTS["skill"]
        weight_total += WEIGHTS["skill"]
    if title_score is not None:
        weighted_sum += title_score * WEIGHTS["title"]
        weight_total += WEIGHTS["title"]
    if experience_score is not None:
        weighted_sum += experience_score * WEIGHTS["experience"]
        weight_total += WEIGHTS["experience"]
    if location_score is not None:
        weighted_sum += location_score * WEIGHTS["location"]
        weight_total += WEIGHTS["location"]
    if salary_score is not None:
        weighted_sum += salary_score * WEIGHTS["salary"]
        weight_total += WEIGHTS["salary"]
    if visa_score is not None:
        weighted_sum += visa_score * WEIGHTS["visa"]
        weight_total += WEIGHTS["visa"]
    
    if weight_total > 0:
        overall = (weighted_sum / weight_total) * 100
        scores.overall_score = round(overall, 2)
    else:
        scores.overall_score = None
    
    # Calculate interview probability
    scores.interview_probability = round(
        calculate_interview_probability(scores), 2
    )
    
    # Get recommendation
    if scores.overall_score is not None:
        scores.recommendation = get_recommendation(scores.overall_score)
    else:
        scores.recommendation = "hold"  # Default to hold if can't score
    
    logger.debug(
        "candidate_scored",
        candidate_id=candidate.id,
        job_id=job.id,
        overall=scores.overall_score,
        recommendation=scores.recommendation,
    )
    
    return scores


async def get_all_candidate_scores(
    db: AsyncSession,
    job: Job,
) -> list[tuple[Candidate, MatchScores]]:
    """Score a job against all active candidates.
    
    Args:
        db: Database session.
        job: Job to score.
    
    Returns:
        List of (Candidate, MatchScores) tuples sorted by score.
    """
    result = await db.execute(
        select(Candidate).where(Candidate.status == "active")
    )
    candidates = list(result.scalars().all())
    
    scored = []
    for candidate in candidates:
        scores = await score_candidate_job(db, candidate, job)
        scored.append((candidate, scores))
    
    # Sort by overall score descending
    scored.sort(
        key=lambda x: x[1].overall_score or 0,
        reverse=True,
    )
    
    return scored


async def get_applications_today(
    db: AsyncSession,
    candidate_id: str,
) -> int:
    """Get number of applications submitted today by a candidate."""
    today = datetime.now(UTC).date()
    
    result = await db.execute(
        select(Application)
        .where(Application.candidate_id == candidate_id)
        .where(Application.status == "submitted")
    )
    apps = result.scalars().all()
    
    count = 0
    for app in apps:
        if app.applied_at and app.applied_at.date() == today:
            count += 1
    
    return count


async def get_company_application_count(
    db: AsyncSession,
    candidate_id: str,
    company: str,
) -> int:
    """Get number of applications to same company."""
    result = await db.execute(
        select(Job).where(Job.company == company)
    )
    jobs = list(result.scalars().all())
    job_ids = [j.id for j in jobs]
    
    if not job_ids:
        return 0
    
    result = await db.execute(
        select(Application)
        .where(Application.candidate_id == candidate_id)
        .where(Application.job_id.in_(job_ids))
    )
    return len(result.scalars().all())


async def allocate_best_candidate(
    db: AsyncSession,
    job: Job,
    candidates: list[Candidate],
    all_scores: list[MatchScores],
    target_volume: int = 10,
) -> Candidate | None:
    """Allocate the best candidate for a job when multiple match.
    
    Selection criteria (per blueprint):
    1. Best-fit candidate (highest overall score)
    2. Priority candidate (by readiness_score)
    3. Candidate with lower daily apply count
    4. Candidate with higher interview probability
    5. Candidate not already applied to same company/job
    
    Args:
        db: Database session.
        job: Job to allocate to.
        candidates: List of candidates.
        all_scores: Their match scores.
        target_volume: Target applications per day.
    
    Returns:
        Best candidate to allocate, or None if none suitable.
    """
    allocations = []
    
    for candidate, scores in zip(candidates, all_scores):
        if scores.recommendation in ("skip",) or scores.overall_score is None:
            continue
        
        # Get applications today
        apps_today = await get_applications_today(db, candidate.id)
        
        # Check if at limit
        if apps_today >= (candidate.daily_apply_limit or target_volume):
            continue
        
        # Check if already applied to this company
        company_apps = await get_company_application_count(
            db, candidate.id, job.company
        )
        
        allocation = AllocationCandidate(
            candidate_id=candidate.id,
            overall_score=scores.overall_score or 0,
            interview_probability=scores.interview_probability or 0,
            applications_today=apps_today,
            daily_apply_limit=candidate.daily_apply_limit or target_volume,
            applications_to_same_company=company_apps,
        )
        allocations.append((candidate, allocation, scores))
    
    if not allocations:
        return None
    
    # Sort by allocation priority (per blueprint criteria)
    # 1. Highest overall score
    # 2. Highest interview probability
    # 3. Lowest applications today (room for more)
    # 4. Not applied to same company
    allocations.sort(
        key=lambda x: (
            -x[1].overall_score,
            -x[1].interview_probability,
            x[1].applications_today,
            x[1].applications_to_same_company,
        ),
    )
    
    return allocations[0][0]  # Return best candidate


async def create_application_with_matching(
    db: AsyncSession,
    candidate: Candidate,
    job: Job,
    resume_id: str | None = None,
) -> Application:
    """Create an application with automated matching scores.
    
    Args:
        db: Database session.
        candidate: Candidate applying.
        job: Job to apply to.
        resume_id: Optional resume ID.
    
    Returns:
        Created Application with scores.
    """
    # Calculate match scores
    scores = await score_candidate_job(db, candidate, job)
    
    # Create application
    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        resume_id=resume_id or candidate.primary_resume_id,
        status="matched",
        skill_score=scores.skill_score,
        title_score=scores.title_score,
        experience_score=scores.experience_score,
        location_score=scores.location_score,
        salary_score=scores.salary_score,
        visa_score=scores.visa_score,
        interview_probability=scores.interview_probability,
    )
    
    # Determine initial status based on recommendation
    if scores.recommendation == "apply_immediate":
        application.status = "ready_to_apply"
    elif scores.recommendation == "apply_if_volume":
        application.status = "matched"
    elif scores.recommendation == "hold":
        application.status = "matched"  # Hold in matched state
    else:  # skip
        application.status = "matched"  # Still record but will be skipped
    
    db.add(application)
    await db.commit()
    await db.refresh(application)
    
    logger.info(
        "application_created_with_matching",
        application_id=application.id,
        candidate_id=candidate.id,
        job_id=job.id,
        overall_score=scores.overall_score,
        recommendation=scores.recommendation,
    )
    
    return application
"""Cover Letter Generation Service.

Per blueprint:
- Cover letter generation based on candidate-job fit
- Template-based generation
- AI-enhanced generation
"""

from enum import Enum
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.job import Job

logger = structlog.get_logger(__name__)


class CoverLetterStyle(str, Enum):
    """Cover letter styles."""
    FORMAL = "formal"
    PROFESSIONAL = "professional"
    CREATIVE = "creative"
    MINIMAL = "minimal"


# Cover letter templates
COVER_LETTER_TEMPLATES = {
    "formal": """Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company}. 
With my extensive experience in {key_skills} and a proven track record of delivering results, 
I am confident that I would be a valuable addition to your team.

In my current role, I have demonstrated {achievements}. 
This experience directly aligns with the requirements outlined in your job posting, 
particularly regarding {relevant_skills}.

I am excited about the opportunity to contribute to {company}'s continued success 
and would welcome the chance to discuss how my background fits your needs.

Thank you for your consideration.

Sincerely,
{candidate_name}""",
    
    "professional": """Dear {company} Team,

I am thrilled to apply for the {job_title} role at {company}. 
With {years_experience} years of experience in {key_skills}, 
I have developed a passion for building great products and solving complex problems.

What draws me to {company} is your commitment to innovation and your focus on {company_values}. 
I believe my skills in {relevant_skills} would allow me to make an immediate impact.

I would love to discuss how my background aligns with your team's goals.

Best regards,
{candidate_name}""",
    
    "creative": """Hey {company}!

When I saw the {job_title} opening, I had to apply. 
Your work on {company_product} has inspired me, and I see this as the perfect 
opportunity to join your mission.

As someone who thrives on {key_strengths}, I bring a unique perspective 
and a genuine excitement for what you are building.

Let's chat about how I can contribute to something great!

Cheers,
{candidate_name}""",
    
    "minimal": """I am interested in the {job_title} position at {company}.

My background in {key_skills} and experience with {relevant_skills} 
make me a strong candidate for this role.

I look forward to hearing from you.

{candidate_name}""",
}


async def generate_cover_letter(
    db: AsyncSession,
    candidate: Candidate,
    job: Job,
    style: str = "professional",
) -> dict[str, Any]:
    """Generate a cover letter for a job application.
    
    Per blueprint:
    1. Receive job description
    2. Compare with candidate
    3. Choose best resume
    4. Tailor if needed
    5. Generate cover letter if required
    6. Send to application queue
    
    Args:
        db: Database session.
        candidate: Candidate applying.
        job: Job to apply to.
        style: Cover letter style (formal, professional, creative, minimal).
    
    Returns:
        Generated cover letter data.
    """
    # Get template
    template = COVER_LETTER_TEMPLATES.get(style, COVER_LETTER_TEMPLATES["professional"])
    
    # Build variables
    variables = await _build_cover_letter_variables(candidate, job)
    
    # Fill template
    letter = template.format(**variables)
    
    return {
        "content": letter,
        "style": style,
        "candidate_id": candidate.id,
        "job_id": job.id,
        "word_count": len(letter.split()),
    }


async def _build_cover_letter_variables(
    candidate: Candidate,
    job: Job,
) -> dict[str, Any]:
    """Build variables for cover letter template."""
    
    # Extract skills (simplified)
    key_skills = _extract_key_skills(candidate, job)
    
    # Get experience
    years_exp = candidate.years_experience or "5"
    
    # Build company values based on JD
    company_values = _extract_company_focus(job.description)
    company_product = _extract_product_focus(job.company)
    
    return {
        "job_title": job.title,
        "company": job.company,
        "candidate_name": f"{candidate.first_name} {candidate.last_name}",
        "key_skills": ", ".join(key_skills[:3]),
        "relevant_skills": ", ".join(key_skills[:5]),
        "years_experience": years_exp,
        "achievements": "delivering high-impact projects and leading cross-functional teams",
        "key_strengths": "creativity and problem-solving",
        "company_values": company_values or "innovation",
        "company_product": company_product or "technology",
    }


def _extract_key_skills(candidate: Candidate, job: Job) -> list[str]:
    """Extract key skills for cover letter.
    
    Combines candidate skills with job-required skills.
    """
    skills = []
    
    # Add candidate skills
    if candidate.skill_confidence:
        skills.extend(list(candidate.skill_confidence.keys())[:5])
    
    # Add job skills
    if job.skills_required and isinstance(job.skills_required, dict):
        for skill_list in job.skills_required.values():
            if isinstance(skill_list, list):
                skills.extend(skill_list[:3])
    
    # Deduplicate and return
    return list(dict.fromkeys(skills))


def _extract_company_focus(description: str) -> str | None:
    """Extract company's focus area from JD."""
    description_lower = description.lower()
    
    if "ai" in description_lower or "machine learning" in description_lower:
        return "AI and machine learning"
    if "cloud" in description_lower or "aws" in description_lower:
        return "cloud computing"
    if "mobile" in description_lower:
        return "mobile development"
    if "web" in description_lower or "frontend" in description_lower:
        return "web development"
    if "data" in description_lower or "analytics" in description_lower:
        return "data-driven solutions"
    
    return None


def _extract_product_focus(company: str) -> str | None:
    """Extract product focus based on company name."""
    company_lower = company.lower()
    
    if "google" in company_lower:
        return "search and cloud technology"
    if "amazon" in company_lower or "aws" in company_lower:
        return "e-commerce and cloud services"
    if "microsoft" in company_lower:
        return "enterprise software"
    if "meta" in company_lower or "facebook" in company_lower:
        return "social technology"
    
    return "technology"


async def generate_ai_cover_letter(
    candidate: Candidate,
    job: Job,
    additional_context: str | None = None,
) -> dict[str, Any]:
    """Generate AI-enhanced cover letter.
    
    Uses LLM to create personalized, compelling cover letter.
    
    Args:
        candidate: Candidate applying.
        job: Job to apply to.
        additional_context: Any additional context to include.
    
    Returns:
        AI-generated cover letter.
    """
    # Build prompt
    prompt = f"""Generate a compelling cover letter for a job application.

Candidate:
- Name: {candidate.first_name} {candidate.last_name}
- Target Role: {candidate.target_role}
- Key Skills: {', '.join(list(candidate.skill_confidence or {}).keys())[:5]}
- Experience: {candidate.years_experience} years

Job:
- Title: {job.title}
- Company: {job.company}
- Description: {job.description[:1000]}

{"Additional Context: " + additional_context if additional_context else ""}

Write in a {candidate.target_role or 'professional'} tone. 
Keep it to 3 paragraphs max. 
Be specific about qualifications and why this company.
"""
    
    # In production, this would call LLM
    # For now, return basic version
    result = await generate_cover_letter(
        None,  # No DB needed for basic generation
        candidate,
        job,
        style="professional",
    )
    
    result["method"] = "template"  # Would be "ai" in production
    
    return result


async def should_generate_cover_letter(
    job: Job,
    application_type: str,
) -> bool:
    """Determine if cover letter should be generated.
    
    Args:
        job: Job to apply to.
        application_type: Type of application (easy_apply, job_board, ats, company).
    
    Returns:
        True if cover letter recommended.
    """
    # Check if JD suggests cover letter required
    desc_lower = job.description.lower()
    
    if "cover letter required" in desc_lower or "cover letter mandatory" in desc_lower:
        return True
    
    # ATS applications usually benefit
    if application_type in ["ats", "company"]:
        return True
    
    # Job board varies by platform
    if application_type == "job_board":
        # Check platform tendencies
        if "indeed" in (job.platform or "").lower():
            return False  # Indeed doesn't typically use
        return True
    
    return False
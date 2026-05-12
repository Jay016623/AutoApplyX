"""AI-Enhanced Match Brain using LLM for complex matching decisions.

This module provides AI-powered matching for:
- Parsing job descriptions to extract structured requirements
- Matching unstructured text (extracting skills from JD text)
- Handling ambiguous cases where rule-based matching isn't sufficient
- Generating match explanations for operators
"""

from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.core.llm.client import LLMClient

logger = structlog.get_logger(__name__)


class JobRequirements(BaseModel):
    """Extracted requirements from a job description using AI."""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_range: str | None = None
    education_level: str | None = None
    visa_sponsorship_likely: bool | None = None
    remote_possible: bool | None = None
    salary_range_estimate: str | None = None
    key_phrases: list[str] = Field(default_factory=list)


class MatchExplanation(BaseModel):
    """AI-generated explanation for a match decision."""
    summary: str
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    interview_tips: list[str] = Field(default_factory=list)


AIIOSystemPrompt = """You are an expert job matching AI for a candidate marketing automation system.
Your role is to analyze job descriptions and candidate profiles to determine fit.

For each match, you should:
1. Extract key requirements from job descriptions
2. Identify candidate strengths relative to requirements  
3. Provide honest assessments of fit quality
4. Suggest interview topics based on the match

Be concise and actionable in your analysis."""


JD_EXTRACTION_PROMPT = """Extract structured requirements from this job description.

Job Title: {title}
Company: {company}

Job Description:
{description}

Extract and return as JSON:
{{
    "required_skills": ["skill1", "skill2"],
    "preferred_skills": ["skill3"],
    "experience_range": "X-Y years",
    "education_level": "bachelor/master/PhD",
    "visa_sponsorship_likely": true/false,
    "remote_possible": true/false,
    "salary_range_estimate": "$X-$Y",
    "key_phrases": ["important phrase 1"]
}}

Only include fields where you have clear evidence. Use null for uncertain fields."""


MATCH_EXPLANATION_PROMPT = """Generate a match explanation for this candidate-job pair.

Candidate Profile:
- Name: {candidate_name}
- Target Role: {target_role}
- Skills: {skills}
- Years Experience: {years_experience}
- Location: {location}
- Visa Status: {visa_status}

Job:
- Title: {job_title}
- Company: {job_company}
- Skills Required: {job_skills}
- Experience Required: {job_experience}
- Location: {job_location}

Match Scores:
- Overall: {overall_score}
- Skill: {skill_score}
- Title: {title_score}
- Experience: {experience_score}
- Location: {location_score}
- Salary: {salary_score}
- Visa: {visa_score}

Return as JSON:
{{
    "summary": "2-3 sentence summary of fit quality",
    "strengths": ["key strength 1", "key strength 2"],
    "concerns": ["potential concern 1"],
    "interview_tips": ["tip for aceing the interview"]
}}"""


class AIMatchBrain:
    """AI-enhanced matching using LLM for complex decisions."""

    def __init__(self):
        self._llm = LLMClient()

    async def extract_job_requirements(
        self,
        title: str,
        company: str,
        description: str,
    ) -> JobRequirements:
        """Extract structured requirements from a job description.
        
        Uses AI to parse unstructured JD text and extract:
        - Required/preferred skills
        - Experience requirements
        - Education requirements
        - Visa sponsorship signals
        - Remote work possibility
        - Salary estimates
        
        Args:
            title: Job title.
            company: Company name.
            description: Full job description text.
        
        Returns:
            JobRequirements with extracted data.
        """
        prompt = JD_EXTRACTION_PROMPT.format(
            title=title,
            company=company,
            description=description[:4000],  # Limit context
        )

        try:
            result = await self._llm.complete_with_structured_output(
                prompt=prompt,
                output_schema=JobRequirements,
                system_prompt=AIIOSystemPrompt,
                purpose="jd_extraction",
            )
            logger.info(
                "jd_requirements_extracted",
                title=title,
                required_skills=len(result.required_skills),
            )
            return result
        except Exception as e:
            logger.error(
                "jd_extraction_failed",
                title=title,
                error=str(e),
            )
            return JobRequirements()  # Return empty on failure

    async def explain_match(
        self,
        candidate_data: dict[str, Any],
        job_data: dict[str, Any],
        scores: dict[str, float],
    ) -> MatchExplanation:
        """Generate human-readable explanation for a match decision.
        
        Args:
            candidate_data: Candidate profile data.
            job_data: Job data.
            scores: Match scores dictionary.
        
        Returns:
            MatchExplanation with details.
        """
        prompt = MATCH_EXPLANATION_PROMPT.format(
            candidate_name=candidate_data.get("full_name", "Unknown"),
            target_role=candidate_data.get("target_role", "N/A"),
            skills=", ".join(
                candidate_data.get("skill_confidence", {}).keys()
            ),
            years_experience=candidate_data.get("years_experience", "N/A"),
            location=candidate_data.get("location", "N/A"),
            visa_status=candidate_data.get("visa_status", "N/A"),
            job_title=job_data.get("title", "N/A"),
            job_company=job_data.get("company", "N/A"),
            job_skills=", ".join(job_data.get("skills_required", [])),
            job_experience=job_data.get("experience_level", "N/A"),
            job_location=job_data.get("location", "N/A"),
            overall_score=scores.get("overall_score", "N/A"),
            skill_score=scores.get("skill_score", "N/A"),
            title_score=scores.get("title_score", "N/A"),
            experience_score=scores.get("experience_score", "N/A"),
            location_score=scores.get("location_score", "N/A"),
            salary_score=scores.get("salary_score", "N/A"),
            visa_score=scores.get("visa_score", "N/A"),
        )

        try:
            result = await self._llm.complete_with_structured_output(
                prompt=prompt,
                output_schema=MatchExplanation,
                system_prompt=AIIOSystemPrompt,
                purpose="match_explanation",
            )
            return result
        except Exception as e:
            logger.error(
                "match_explanation_failed",
                error=str(e),
            )
            return MatchExplanation(
                summary="Match analysis unavailable.",
            )

    async def improve_scores_with_ai(
        self,
        job: "Job",
        candidate: "Candidate",
        rule_scores: dict[str, float],
    ) -> dict[str, float]:
        """Use AI to improve/match scores where rules fall short.
        
        For skills that couldn't be scored by rules, use AI to:
        1. Check if candidate skills match JD text
        2. Consider overall fit factors
        
        Args:
            job: Job object.
            candidate: Candidate object.
            rule_scores: Already calculated rule-based scores.
        
        Returns:
            Updated scores dict with AI-assisted improvements.
        """
        scores = rule_scores.copy()
        
        # If skill score is None, try to extract and match with AI
        if scores.get("skill_score") is None:
            requirements = await self.extract_job_requirements(
                title=job.title,
                company=job.company,
                description=job.description,
            )
            
            # Match against extracted skills
            if requirements.required_skills and candidate.skill_confidence:
                candidate_skills = set(candidate.skill_confidence.keys())
                required = set(
                    s.lower() for s in requirements.required_skills
                )
                
                matches = candidate_skills & required
                if required:
                    ai_score = (len(matches) / len(required)) * 100
                    scores["skill_score"] = round(ai_score, 2)
        
        return scores


# Singleton instance
_ai_match_brain: AIMatchBrain | None = None


def get_ai_match_brain() -> AIMatchBrain:
    """Get the singleton AIMatchBrain instance."""
    global _ai_match_brain
    if _ai_match_brain is None:
        _ai_match_brain = AIMatchBrain()
    return _ai_match_brain
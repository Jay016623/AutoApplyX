"""Smart Question Answer Engine - Pre-approved answer bank.

Per blueprint:
- Legal/work authorization answers must NEVER be guessed
- Pre-approved answers from candidate
- Repeated question detection
- Safe vs risky question classification
"""

from enum import Enum
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.application_answer import ApplicationAnswer

logger = structlog.get_logger(__name__)


class QuestionCategory(str, Enum):
    """Categories of application questions."""
    WORK_AUTHORIZATION = "work_authorization"
    SALARY = "salary"
    NOTICE_PERIOD = "notice_period"
    RELOCATION = "relocation"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    CONTRACT = "contract"
    AVAILABILITY = "availability"
    SKILLS = "skills"
    CUSTOM = "custom"


# Standard question keys (per blueprint)
STANDARD_QUESTIONS = {
    # Work authorization (CRITICAL - never guess)
    "authorized_to_work": {
        "category": QuestionCategory.WORK_AUTHORIZATION,
        "safe_to_guess": False,
        "required": True,
        "sample_values": ["Yes", "No"],
    },
    "need_sponsorship": {
        "category": QuestionCategory.WORK_AUTHORIZATION,
        "safe_to_guess": False,
        "required": True,
        "sample_values": ["Yes", "No"],
    },
    "work_authorize_disclosure": {
        "category": QuestionCategory.WORK_AUTHORIZATION,
        "safe_to_guess": False,
        "required": True,
    },
    "visa_status": {
        "category": QuestionCategory.WORK_AUTHORIZATION,
        "safe_to_guess": False,
        "required": True,
    },
    
    # Salary (can estimate from range)
    "salary_expectation": {
        "category": QuestionCategory.SALARY,
        "safe_to_guess": False,
        "required": True,
    },
    "current_salary": {
        "category": QuestionCategory.SALARY,
        "safe_to_guess": False,
        "required": False,
    },
    
    # Notice period
    "notice_period": {
        "category": QuestionCategory.NOTICE_PERIOD,
        "safe_to_guess": False,
        "required": False,
    },
    
    # Relocation
    "willing_to_relocate": {
        "category": QuestionCategory.RELOCATION,
        "safe_to_guess": True,
        "required": False,
    },
    "open_to_remote": {
        "category": QuestionCategory.RELOCATION,
        "safe_to_guess": True,
        "required": False,
    },
    
    # Experience
    "years_experience": {
        "category": QuestionCategory.EXPERIENCE,
        "safe_to_guess": True,
        "required": True,
    },
    "years_sql": {
        "category": QuestionCategory.EXPERIENCE,
        "safe_to_guess": False,
        "required": False,
    },
    "years_python": {
        "category": QuestionCategory.EXPERIENCE,
        "safe_to_guess": False,
        "required": False,
    },
    
    # Education
    "highest_education": {
        "category": QuestionCategory.EDUCATION,
        "safe_to_guess": True,
        "required": False,
    },
    "degree_field": {
        "category": QuestionCategory.EDUCATION,
        "safe_to_guess": True,
        "required": False,
    },
    
    # Contract/Hours
    "open_to_contract": {
        "category": QuestionCategory.CONTRACT,
        "safe_to_guess": True,
        "required": False,
    },
    "open_to_onsite": {
        "category": QuestionCategory.AVAILABILITY,
        "safe_to_guess": True,
        "required": False,
    },
    "available_start_date": {
        "category": QuestionCategory.AVAILABILITY,
        "safe_to_guess": False,
        "required": False,
    },
}


def normalize_question_key(question_text: str) -> str | None:
    """Normalize question text to standard key.
    
    Args:
        question_text: The question as displayed.
    
    Returns:
        Standard key or None.
    """
    text_lower = question_text.lower().strip()
    
    # Direct match
    for key in STANDARD_QUESTIONS:
        if key in text_lower or text_lower in key:
            return key
    
    # Fuzzy matching
    if "authorize" in text_lower and "work" in text_lower:
        return "authorized_to_work"
    if "sponsor" in text_lower:
        return "need_sponsorship"
    if "salary" in text_lower or "compensation" in text_lower:
        return "salary_expectation"
    if "notice" in text_lower:
        return "notice_period"
    if "relocate" in text_lower:
        return "willing_to_relocate"
    if "remote" in text_lower:
        return "open_to_remote"
    if "years" in text_lower and "experience" in text_lower:
        return "years_experience"
    if "sql" in text_lower:
        return "years_sql"
    if "python" in text_lower:
        return "years_python"
    if "education" in text_lower or "degree" in text_lower:
        return "highest_education"
    if "contract" in text_lower:
        return "open_to_contract"
    if "onsite" in text_lower:
        return "open_to_onsite"
    
    return None


async def get_answer(
    db: AsyncSession,
    candidate_id: str,
    question_key: str,
) -> ApplicationAnswer | None:
    """Get candidate's pre-approved answer for a question.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        question_key: Standard question key.
    
    Returns:
        Answer or None.
    """
    result = await db.execute(
        select(ApplicationAnswer)
        .where(ApplicationAnswer.candidate_id == candidate_id)
        .where(ApplicationAnswer.question_key == question_key)
    )
    return result.scalar_one_or_none()


async def get_answer_value(
    db: AsyncSession,
    candidate_id: str,
    question_text: str,
    default_value: str | None = None,
) -> str | None:
    """Get answer value for a question, with fallback.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        question_text: Question as displayed.
        default_value: Default if no answer found.
    
    Returns:
        Answer value.
    """
    # Normalize to key
    question_key = normalize_question_key(question_text)
    
    if not question_key:
        # Use text as key for unknown questions
        question_key = question_text.lower().strip()
    
    # Get from answer bank
    if db:
        answer = await get_answer(db, candidate_id, question_key)
        if answer:
            return answer.answer_value
    
    # Also check candidate answer_bank JSON
    result = await db.execute(
        select(Candidate).where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if candidate and candidate.answer_bank:
        bank = candidate.answer_bank
        if question_key in bank:
            return bank[question_key]
    
    return default_value


async def answer_question(
    db: AsyncSession,
    candidate_id: str,
    question_text: str,
) -> dict[str, Any]:
    """Get answer for an application question.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        question_text: Question as displayed.
    
    Returns:
        Answer data with risk assessment.
    """
    # Get answer
    answer_value = await get_answer_value(db, candidate_id, question_text)
    
    # Determine risk level
    question_key = normalize_question_key(question_text)
    risk_info = await classify_question_risk(question_key or question_text)
    
    result = {
        "question_text": question_text,
        "question_key": question_key,
        "answer": answer_value,
        "risk_level": risk_info.get("risk_level", "unknown"),
        "safe_to_auto_fill": risk_info.get("safe", True),
        "category": risk_info.get("category", QuestionCategory.CUSTOM),
    }
    
    # Track if needs approval
    if not answer_value and not risk_info.get("safe", True):
        result["needs_candidate_approval"] = True
        result["escalate"] = True
    
    return result


async def classify_question_risk(question_key: str) -> dict[str, Any]:
    """Classify question risk level.
    
    Args:
        question_key: Question key.
    
    Returns:
        Risk classification.
    """
    # Get question info
    q_info = STANDARD_QUESTIONS.get(question_key, {})
    
    category = q_info.get("category", QuestionCategory.CUSTOM)
    safe_to_guess = q_info.get("safe_to_guess", True)
    required = q_info.get("required", False)
    
    # Classify risk
    if not safe_to_guess:
        risk_level = "high" if required else "medium"
    elif required:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    return {
        "question_key": question_key,
        "category": category.value if isinstance(category, Enum) else category,
        "risk_level": risk_level,
        "safe": safe_to_guess,
        "required": required,
    }


async def create_answer_from_candidate(
    db: AsyncSession,
    candidate_id: str,
    question_key: str,
    answer_value: str,
    verify: bool = False,
) -> ApplicationAnswer:
    """Create a pre-approved answer from candidate.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        question_key: Standard question key.
        answer_value: Candidate's answer.
        verify: Whether answer is verified by candidate.
    
    Returns:
        Created answer.
    """
    answer = ApplicationAnswer(
        candidate_id=candidate_id,
        question_key=question_key,
        answer_value=answer_value,
        answer_type="text",
        is_verified=verify,
        verified_at=datetime.now().isoformat() if verify else None,
    )
    
    db.add(answer)
    await db.commit()
    await db.refresh(answer)
    
    logger.info(
        "answer_created",
        candidate_id=candidate_id,
        question_key=question_key,
        verified=verify,
    )
    
    return answer


async def get_screening_answers(
    db: AsyncSession,
    candidate_id: str,
    questions: list[str],
) -> list[dict[str, Any]]:
    """Get answers for multiple screening questions.
    
    Args:
        db: Database session.
        candidate_id: Candidate ID.
        questions: List of question texts.
    
    Returns:
        List of answer data.
    """
    answers = []
    
    for question in questions:
        answer = await answer_question(db, candidate_id, question)
        answers.append(answer)
    
    return answers


from datetime import datetime
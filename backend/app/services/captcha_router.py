"""Captcha Router - Handle captcha friction in automation.

Per blueprint:
- Detect captcha
- Classify captcha type
- Retry safely
- Switch session if possible
- Route to operator assist mode
- Track captcha-heavy portals

Captcha is not fully automatable. Goal is fast routing and reduced blockage.
"""

from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CaptchaType(str, Enum):
    """Types of captchas."""
    IMAGE = "image"           # Select images (I'm not a robot)
    CHECKBOX = "checkbox"     # Click checkbox (reCAPTCHA v2)
    SLIDER = "slider"        # Slider puzzle
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"     # hCaptcha
    CUSTOM = "custom"        # Portal-specific custom
    UNKNOWN = "unknown"


class CaptchaStatus(str, Enum):
    """Captcha resolution status."""
    ENCOUNTERED = "encountered"
    BYPASSED = "bypassed"
    FAILED = "failed"
    OPERATOR_SOLVED = "operator_solved"


# Portal captcha metadata
CAPTCHA_PORTAL_INFO = {
    "linkedin": {
        "captcha_types": ["recaptcha_v3", "custom"],
        "frequency": "medium",
        "autoolvable": True,
    },
    "indeed": {
        "captcha_types": ["recaptcha_v2", "checkbox"],
        "frequency": "high",
        "autoolvable": False,
    },
    "dice": {
        "captcha_types": ["custom"],
        "frequency": "low",
        "autoolvable": True,
    },
    "monster": {
        "captcha_types": ["recaptcha_v2"],
        "frequency": "medium",
        "autoolvable": False,
    },
    "glassdoor": {
        "captcha_types": ["recaptcha_v2", "hcaptcha"],
        "frequency": "high",
        "autoolvable": False,
    },
    "ziprecruiter": {
        "captcha_types": ["slider"],
        "frequency": "medium",
        "autoolvable": True,
    },
}


async def detect_captcha_type(
    page_html: str,
    url: str,
) -> str | None:
    """Detect captcha type from page HTML/URL.
    
    Args:
        page_html: Page HTML content.
        url: Page URL.
    
    Returns:
        Detected captcha type or None.
    """
    url_lower = url.lower()
    
    # Check for reCAPTCHA v2
    if 'name="g-recaptcha-response"' in page_html or "recaptcha/api" in page_html:
        if "v2" in page_html or "checkbox" in page_html:
            return CaptchaType.RECAPTCHA_V2
        return CaptchaType.RECAPTCHA_V3
    
    # Check for hCaptcha
    if "hcaptcha" in page_html or "h-captcha" in page_html:
        return CaptchaType.HCAPTCHA
    
    # Check for slider
    if "slider" in page_html or "puzzle" in page_html:
        return CaptchaType.SLIDER
    
    # Check URL patterns
    if "indeed" in url_lower:
        return CaptchaType.RECAPTCHA_V2
    if "linkedin" in url_lower:
        return CaptchaType.RECAPTCHA_V3
    if "dice" in url_lower:
        return CaptchaType.CUSTOM
    
    # Check for generic checkbox captcha
    if 'class="recaptcha"' in page_html.lower():
        return CaptchaType.CHECKBOX
    
    # Check for image selection
    if "select all images" in page_html.lower() or "im not a robot" in page_html.lower():
        return CaptchaType.IMAGE
    
    return None


async def classify_captcha(
    page_html: str,
    url: str,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Classify captcha and determine resolution approach.
    
    Args:
        page_html: Page HTML.
        url: Page URL.
        error_message: Any error message.
    
    Returns:
        Classification with recommended action.
    """
    captcha_type = await detect_captcha_type(page_html, url)
    
    if not captcha_type:
        return {
            "detected": False,
            "type": None,
            "action": "continue",
        }
    
    # Get portal info
    portal = get_portal_from_url(url)
    portal_info = CAPTCHA_PORTAL_INFO.get(portal, {})
    
    # Determine difficulty
    if captcha_type in [CaptchaType.RECAPTCHA_V2, CaptchaType.IMAGE]:
        difficulty = "high"
        autoolvable = False
    elif captcha_type == CaptchaType.SLIDER:
        difficulty = "medium"
        autoolvable = True
    elif captcha_type == CaptchaType.RECAPTCHA_V3:
        # v3 is token-based, can be solved with service
        difficulty = "medium"
        autoolvable = True
    else:
        difficulty = "unknown"
        autoolvable = portal_info.get("autoolvable", False)
    
    # Recommended action
    if autoolvable:
        action = "auto_solve"
    else:
        action = "operator_escalate"
    
    return {
        "detected": True,
        "type": captcha_type,
        "portal": portal,
        "difficulty": difficulty,
        "autoolvable": autoolvable,
        "action": action,
        "portal_info": portal_info,
    }


async def get_portal_from_url(url: str) -> str | None:
    """Extract portal name from URL.
    
    Args:
        url: Application URL.
    
    Returns:
        Portal name or None.
    """
    url_lower = url.lower()
    
    portals = ["linkedin", "indeed", "dice", "monster", "glassdoor", "ziprecruiter"]
    
    for portal in portals:
        if portal in url_lower:
            return portal
    
    # Check for company portal
    if "/careers/" in url_lower or "/jobs/" in url_lower:
        return "company_portal"
    
    return "unknown"


async def handle_captcha_encounter(
    candidate_id: str,
    application_id: str,
    portal: str,
    captcha_type: str,
    classification: dict[str, Any],
) -> dict[str, Any]:
    """Handle captcha encounter - decide action.
    
    Args:
        candidate_id: Candidate ID.
        application_id: Application ID.
        portal: Portal name.
        captcha_type: Type of captcha.
        classification: Classification result.
    
    Returns:
        Action to take with details.
    """
    action = classification.get("action", "operator_escalate")
    
    if action == "auto_solve":
        return {
            "action": "auto_solve",
            "method": "captcha_service",
            "captcha_type": captcha_type,
            "candidate_id": candidate_id,
            "application_id": application_id,
            "portal": portal,
        }
    elif action == "operator_escalate":
        return {
            "action": "escalate",
            "task_type": "captcha_entry",
            "captcha_type": captcha_type,
            "candidate_id": candidate_id,
            "application_id": application_id,
            "portal": portal,
            "instructions": f"Enter captcha for {portal} ({captcha_type})",
            "priority": 8,  # Captcha blocking = high priority
        }
    
    return {
        "action": "skip",
        "reason": "unhandled_captcha_type",
    }


async def should_switch_session(
    captcha_count: int,
    time_window_minutes: int = 30,
) -> bool:
    """Determine if session should be switched due to captcha fatigue.
    
    Args:
        captcha_count: Captchas encountered in time window.
        time_window_minutes: Time window to consider.
    
    Returns:
        True if should switch.
    """
    # Threshold based on frequency
    threshold = 3
    
    if captcha_count >= threshold:
        logger.info(
            "session_switch_recommended",
            captcha_count=captcha_count,
            threshold=threshold,
        )
        return True
    
    return False


async def get_captcha_heavy_portals() -> list[dict[str, Any]]:
    """Get list of portals known for heavy captcha.
    
    Returns:
        List of portal info.
    """
    heavy_portals = []
    
    for portal, info in CAPTCHA_PORTAL_INFO.items():
        if info.get("frequency") == "high":
            heavy_portals.append({
                "portal": portal,
                "captcha_types": info.get("captcha_types"),
                "frequency": info.get("frequency"),
                "recommendation": "use_proxy" if not info.get("autoolvable") else "auto_solve",
            })
    
    return heavy_portals


async def track_captcha_encounter(
    candidate_id: str,
    application_id: str,
    portal: str,
    captcha_type: str,
    status: str,
    resolution_method: str | None = None,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Track captcha encounter for analytics.
    
    Args:
        candidate_id: Candidate ID.
        application_id: Application ID.
        portal: Portal name.
        captcha_type: Type of captcha.
        status: Resolution status.
        resolution_method: How it was resolved.
        duration_seconds: Time to solve.
    
    Returns:
        Tracking record.
    """
    record = {
        "candidate_id": candidate_id,
        "application_id": application_id,
        "portal": portal,
        "captcha_type": captcha_type,
        "status": status,
        "resolution_method": resolution_method,
        "duration_seconds": duration_seconds,
    }
    
    logger.info("captcha_encounter_tracked", **record)
    
    return record
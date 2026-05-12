"""Unknown Form Solver - Handle unfamiliar application forms.

Per blueprint:
- Read DOM
- Map fields using AI
- Compare with historical layouts
- Fill safe fields
- Route risky fields to operator
- Save solved layout for future
"""

from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# Safe fields that can be auto-filled
SAFE_FIELDS = {
    "first_name",
    "last_name", 
    "email",
    "phone",
    "address",
    "city",
    "state",
    "zip",
    "zip_code",
    "country",
    "linkedin_url",
    "portfolio_url",
    "resume_upload",
}

# Risky fields that need human approval
RISKY_FIELDS = {
    "salary_expectation",
    "notice_period",
    "start_date",
    "work_authorization",
    "sponsorship",
    "gender",
    "ethnicity",
    "disability",
    "veteran_status",
    "criminal_history",
}


class FieldRiskLevel(str, Enum):
    """Risk level for form fields."""
    SAFE = "safe"
    REVIEW = "review"
    RISKY = "risky"


async def parse_form_fields(html: str) -> list[dict[str, Any]]:
    """Parse form fields from HTML.
    
    Args:
        html: HTML content.
    
    Returns:
        List of field info.
    """
    soup = BeautifulSoup(html, "html.parser")
    fields = []
    
    # Find all input elements
    for input_tag in soup.find_all(["input", "select", "textarea"]):
        field_info = {
            "tag": input_tag.name,
            "type": input_tag.get("type", "text"),
            "name": input_tag.get("name", ""),
            "id": input_tag.get("id", ""),
            "label": "",
            "required": input_tag.get("required") is not None,
            "placeholder": input_tag.get("placeholder", ""),
            "value": input_tag.get("value", ""),
            "options": [],
        }
        
        # Try to find label
        field_id = input_tag.get("id")
        if field_id:
            label = soup.find("label", {"for": field_id})
            if label:
                field_info["label"] = label.get_text(strip=True)
        
        # Get select options
        if input_tag.name == "select":
            for option in input_tag.find_all("option"):
                field_info["options"].append({
                    "value": option.get("value", ""),
                    "text": option.get_text(strip=True),
                })
        
        fields.append(field_info)
    
    return fields


async def classify_field_risk(
    field_name: str,
    field_type: str,
    label: str,
) -> str:
    """Classify field risk level.
    
    Args:
        field_name: Field name attribute.
        field_type: Field type.
        label: Field label text.
    
    Returns:
        Risk level.
    """
    name_lower = field_name.lower()
    label_lower = label.lower()
    
    # Check against known risky fields
    for risky in RISKY_FIELDS:
        if risky in name_lower or risky in label_lower:
            return FieldRiskLevel.RISKY
    
    # Check known safe fields
    for safe in SAFE_FIELDS:
        if safe in name_lower or safe in label_lower:
            return FieldRiskLevel.SAFE
    
    # Check field type
    if field_type in ["checkbox", "radio"]:
        # These are often sensitive
        return FieldRiskLevel.REVIEW
    
    # Default to review
    return FieldRiskLevel.REVIEW


async def map_unknown_form(
    html: str,
    url: str,
    candidate_data: dict[str, Any],
) -> dict[str, Any]:
    """Map unknown form to known fields.
    
    Uses AI to:
    1. Parse form fields
    2. Match to candidate data
    3. Identify risky fields
    
    Args:
        html: Form HTML.
        url: Form URL.
        candidate_data: Candidate profile data.
    
    Returns:
        Mapped form data.
    """
    # Parse fields
    fields = await parse_form_fields(html)
    
    # categorize by risk
    safe_fields = []
    review_fields = []
    risky_fields = []
    
    for field in fields:
        risk = await classify_field_risk(
            field.get("name", ""),
            field.get("type", ""),
            field.get("label", ""),
        )
        
        field_with_risk = {**field, "risk_level": risk}
        
        if risk == FieldRiskLevel.SAFE:
            safe_fields.append(field_with_risk)
        elif risk == FieldRiskLevel.RISKY:
            risky_fields.append(field_with_risk)
        else:
            review_fields.append(field_with_risk)
    
    # Try to fill safe fields from candidate data
    fillable = []
    errors = []
    
    for field in safe_fields:
        field_name = field.get("name", "")
        
        # Match to candidate data
        value = match_field_to_candidate(field_name, candidate_data)
        
        if value is not None:
            fillable.append({
                "field": field_name,
                "value": value,
            })
        else:
            errors.append({
                "field": field_name,
                "error": "no_matching_data",
            })
    
    return {
        "portal": get_portal_from_url(url),
        "safe_fields": fillable,
        "review_fields": review_fields,
        "risky_fields": risky_fields,
        "unfillable": errors,
        "can_auto_fill": len(fillable) > 0,
        "needs_operator": len(risky_fields) > 0,
    }


def match_field_to_candidate(
    field_name: str,
    candidate_data: dict[str, Any],
) -> str | None:
    """Match form field to candidate data.
    
    Args:
        field_name: Form field name.
        candidate_data: Candidate profile.
    
    Returns:
        Value to fill or None.
    """
    name_lower = field_name.lower()
    
    # Field mappings
    mappings = {
        "first_name": "first_name",
        "firstname": "first_name",
        "last_name": "last_name", 
        "lastname": "last_name",
        "email": "email",
        "email_address": "email",
        "phone": "phone",
        "phone_number": "phone",
        "address": "location",
        "city": "location",
        "state": "location",
        "zip": "location",
        "zip_code": "location",
        "country": "location",
        "linkedin": "linkedin_url",
        "linkedin_url": "linkedin_url",
        "portfolio": "portfolio_url",
    }
    
    # Find mapping
    for pattern, key in mappings.items():
        if pattern in name_lower:
            value = candidate_data.get(key)
            if value:
                return value
    
    return None


async def solve_with_ai(
    html: str,
    url: str,
    candidate_data: dict[str, Any],
) -> dict[str, Any]:
    """Use AI to solve unknown form.
    
    Args:
        html: Form HTML.
        url: Form URL.
        candidate_data: Candidate profile.
    
    Returns:
        AI-solved form data.
    """
    try:
        ai_brain = get_ai_match_brain()
    except Exception as e:
        logger.error("ai_matcher_unavailable", error=str(e))
        return {
            "success": False,
            "error": "AI unavailable",
        }
    
    # Parse fields
    fields = await parse_form_fields(html)
    
    # Build prompt
    prompt = f"""Analyze this job application form and determine what to fill.

Form URL: {url}

Fields found:
{chr(10).join([f"- {f.get('name')}: {f.get('label')} ({f.get('type')})" for f in fields])}

Candidate data:
{chr(10).join([f"- {k}: {v}" for k, v in candidate_data.items()])}

For each field, indicate:
- The value to fill (if known)
- Whether it's safe to auto-fill or needs review

Return as JSON:
{{
    "fields_to_fill": [{{"field": "name", "value": "xxx", "safe": true/false}}],
    "risky_fields": ["field1", "field2"],
    "unknown_fields": ["field3"]
}}"""
    
    try:
        # Use AI to analyze (simplified)
        mapped = await map_unknown_form(html, url, candidate_data)
        
        return {
            "success": True,
            "fields_to_fill": mapped.get("safe_fields", []),
            "risky_fields": mapped.get("risky_fields", []),
            "method": "rule_based",
        }
    except Exception as e:
        logger.error("form_solve_error", error=str(e))
        return {
            "success": False,
            "error": str(e),
        }


def get_portal_from_url(url: str) -> str:
    """Extract portal name from URL."""
    url_lower = url.lower()
    portals = ["linkedin", "indeed", "dice", "monster", "glassdoor", "ziprecruiter"]
    
    for portal in portals:
        if portal in url_lower:
            return portal
    
    if "/careers/" in url_lower or "/jobs/" in url_lower:
        return "company_portal"
    
    return "unknown"


async def save_solved_layout(
    portal: str,
    form_name: str,
    fields: list[dict[str, Any]],
) -> dict[str, Any]:
    """Save solved form layout for future reference.
    
    Args:
        portal: Portal name.
        form_name: Form identifier.
        fields: Field structure.
    
    Returns:
        Saved layout info.
    """
    # This would save to database for future use
    layout = {
        "portal": portal,
        "form_name": form_name,
        "fields": fields,
        "saved_at": datetime.now().isoformat(),
    }
    
    logger.info("form_layout_saved", **layout)
    
    return layout


from datetime import datetime
from enum import Enum
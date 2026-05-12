"""Business logic service layer.

Modules:
    job_search  -- Job search and CRUD operations
    application -- Application lifecycle management
    resume      -- Resume upload, generation, and scoring
    analytics   -- Dashboard statistics and reporting
    queue       -- Redis-based task queue operations
    match       -- AI Match Brain scoring and candidate allocation
    exception_resolution -- Exception case handling and auto-resolution
    otp_resolution -- OTP auto-fetch and management
    captcha_router -- Captcha detection and routing
    login_recovery -- Login failure recovery
    form_solver -- Unknown form handling
    resume_tailoring -- JD-based resume tailoring
    cover_letter -- Cover letter generation
    smart_answers -- Pre-approved Q&A bank
"""

from app.services import (
    analytics,
    application,
    captcha_router,
    cover_letter,
    exception_resolution,
    form_solver,
    job_search,
    login_recovery,
    match,
    otp_resolution,
    queue,
    resume,
    resume_tailoring,
    smart_answers,
)

__all__ = [
    "analytics",
    "application",
    "captcha_router",
    "cover_letter",
    "exception_resolution",
    "form_solver",
    "job_search",
    "login_recovery",
    "match",
    "otp_resolution",
    "queue",
    "resume",
    "resume_tailoring",
    "smart_answers",
]

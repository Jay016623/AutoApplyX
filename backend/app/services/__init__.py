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
    follow_up -- Automated follow-up sequences
    email_monitor -- Inbox monitoring and classification
    kpi_dashboard -- Analytics and reporting
    auth -- Authentication JWT and password handling
"""

from app.services import (
    analytics,
    application,
    auth,
    captcha_router,
    cover_letter,
    email_monitor,
    exception_resolution,
    follow_up,
    form_solver,
    job_search,
    kpi_dashboard,
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
    "auth",
    "captcha_router",
    "cover_letter",
    "email_monitor",
    "exception_resolution",
    "follow_up",
    "form_solver",
    "job_search",
    "kpi_dashboard",
    "login_recovery",
    "match",
    "otp_resolution",
    "queue",
    "resume",
    "resume_tailoring",
    "smart_answers",
]

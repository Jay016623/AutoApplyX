"""Business logic service layer.

Modules:
    job_search  -- Job search and CRUD operations
    application -- Application lifecycle management
    resume      -- Resume upload, generation, and scoring
    analytics   -- Dashboard statistics and reporting
    queue       -- Redis-based task queue operations
    match       -- AI Match Brain scoring and candidate allocation
"""

from app.services import (
    analytics,
    application,
    job_search,
    match,
    queue,
    resume,
)

__all__ = [
    "analytics",
    "application",
    "job_search",
    "match",
    "queue",
    "resume",
]

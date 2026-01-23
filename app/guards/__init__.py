"""
Guards module - Input validation, rate limiting, and content filtering.
"""
from app.guards.decorators import require_auth, rate_limit_llm
from app.guards.validators import (
    WorkoutGenerationInput,
    WeeklyWorkoutGenerationInput,
    MovementInput,
    PendingWorkoutUpdateInput,
    UserProfileInput,
    ValidationError,
    validate_request,
    VALID_GOALS,
    VALID_EXPERIENCES,
    VALID_SEXES,
)
from app.guards.content_filter import ContentFilter, ContentFilterError
from app.guards.rate_limiter import RateLimiter, RateLimitExceeded

__all__ = [
    # Decorators
    "require_auth",
    "rate_limit_llm",
    # Validators
    "WorkoutGenerationInput",
    "WeeklyWorkoutGenerationInput",
    "MovementInput",
    "PendingWorkoutUpdateInput",
    "UserProfileInput",
    "ValidationError",
    "validate_request",
    "VALID_GOALS",
    "VALID_EXPERIENCES",
    "VALID_SEXES",
    # Content Filter
    "ContentFilter",
    "ContentFilterError",
    # Rate Limiter
    "RateLimiter",
    "RateLimitExceeded",
]

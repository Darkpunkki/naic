"""
Rate Limiter - DB-backed rate limiting for LLM calls.
"""
from datetime import datetime, timedelta
from typing import Optional
import pytz

from app.models import User, db


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit_type: str, reset_time: datetime):
        self.limit_type = limit_type
        self.reset_time = reset_time
        if limit_type == "hour":
            # Calculate minutes until reset (timezone-independent)
            now = datetime.utcnow()
            time_diff = reset_time - now
            minutes_remaining = max(1, int(time_diff.total_seconds() / 60))

            if minutes_remaining < 60:
                self.message = f"Hourly limit reached. Try again in {minutes_remaining} minute{'s' if minutes_remaining != 1 else ''}."
            else:
                hours_remaining = minutes_remaining // 60
                self.message = f"Hourly limit reached. Try again in about {hours_remaining} hour{'s' if hours_remaining != 1 else ''}."
        else:
            self.message = f"Daily limit reached. Try again tomorrow."
        super().__init__(self.message)


class RateLimiter:
    """
    Database-backed rate limiter for LLM API calls.

    Limits:
    - 10 requests per hour
    - 30 requests per day
    """

    HOURLY_LIMIT = 20
    DAILY_LIMIT = 50

    @staticmethod
    def check_and_increment(user_id: int) -> None:
        """
        Check if user is within rate limits and increment counters.

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError("User not found")

        now = datetime.utcnow()

        # Initialize or reset hourly counter
        if user.llm_requests_reset_hour is None or now >= user.llm_requests_reset_hour:
            user.llm_requests_hour = 0
            user.llm_requests_reset_hour = now + timedelta(hours=1)

        # Initialize or reset daily counter
        if user.llm_requests_reset_day is None or now >= user.llm_requests_reset_day:
            user.llm_requests_day = 0
            # Reset at midnight UTC
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            user.llm_requests_reset_day = tomorrow

        # Check hourly limit
        if user.llm_requests_hour >= RateLimiter.HOURLY_LIMIT:
            raise RateLimitExceeded("hour", user.llm_requests_reset_hour)

        # Check daily limit
        if user.llm_requests_day >= RateLimiter.DAILY_LIMIT:
            raise RateLimitExceeded("day", user.llm_requests_reset_day)

        # Increment counters
        user.llm_requests_hour = (user.llm_requests_hour or 0) + 1
        user.llm_requests_day = (user.llm_requests_day or 0) + 1
        db.session.commit()

    @staticmethod
    def get_remaining(user_id: int) -> dict:
        """
        Get remaining requests for a user.

        Returns:
            dict with 'hourly' and 'daily' remaining counts
        """
        user = User.query.get(user_id)
        if not user:
            return {"hourly": 0, "daily": 0}

        now = datetime.utcnow()

        # Check if counters need reset
        hourly_remaining = RateLimiter.HOURLY_LIMIT
        daily_remaining = RateLimiter.DAILY_LIMIT

        if user.llm_requests_reset_hour and now < user.llm_requests_reset_hour:
            hourly_remaining = max(0, RateLimiter.HOURLY_LIMIT - (user.llm_requests_hour or 0))

        if user.llm_requests_reset_day and now < user.llm_requests_reset_day:
            daily_remaining = max(0, RateLimiter.DAILY_LIMIT - (user.llm_requests_day or 0))

        return {
            "hourly": hourly_remaining,
            "daily": daily_remaining,
            "hourly_limit": RateLimiter.HOURLY_LIMIT,
            "daily_limit": RateLimiter.DAILY_LIMIT,
        }

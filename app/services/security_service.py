"""
Security service for rate limiting and abuse prevention.
Tracks email and IP-based security events to prevent spam and abuse.
"""
from datetime import datetime, timedelta
from flask import request

from app.models import db, SecurityEvent


class SecurityService:
    """Security helpers for email and auth operations."""

    # Rate limit thresholds
    EMAIL_VERIFICATION_LIMIT_HOUR = 3
    PASSWORD_RESET_LIMIT_HOUR = 3
    EMAIL_TOTAL_LIMIT_DAY = 5
    IP_LIMIT_HOUR = 10

    @staticmethod
    def _get_client_ip():
        """Get client IP address, handling proxies."""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr or 'unknown'

    @staticmethod
    def check_email_rate_limit(email, event_type):
        """
        Check if email has exceeded rate limits.

        Args:
            email: Email address to check
            event_type: Type of event ('verification_email' or 'reset_email')

        Returns:
            tuple: (allowed: bool, retry_after_seconds: int)
        """
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # Count events in last hour for this specific type
        hour_count = SecurityEvent.query.filter(
            SecurityEvent.email == email,
            SecurityEvent.event_type == event_type,
            SecurityEvent.created_at >= hour_ago
        ).count()

        if event_type == 'verification_email':
            limit = SecurityService.EMAIL_VERIFICATION_LIMIT_HOUR
        else:  # reset_email
            limit = SecurityService.PASSWORD_RESET_LIMIT_HOUR

        if hour_count >= limit:
            # Calculate retry time
            oldest_event = SecurityEvent.query.filter(
                SecurityEvent.email == email,
                SecurityEvent.event_type == event_type,
                SecurityEvent.created_at >= hour_ago
            ).order_by(SecurityEvent.created_at.asc()).first()

            if oldest_event:
                retry_after = int((oldest_event.created_at + timedelta(hours=1) - now).total_seconds())
                return False, max(retry_after, 60)  # Minimum 60 seconds

            return False, 3600  # Default to 1 hour

        # Count all email events in last day
        day_count = SecurityEvent.query.filter(
            SecurityEvent.email == email,
            SecurityEvent.created_at >= day_ago
        ).count()

        if day_count >= SecurityService.EMAIL_TOTAL_LIMIT_DAY:
            return False, 86400  # 24 hours

        return True, 0

    @staticmethod
    def check_ip_rate_limit(event_type):
        """
        Check if IP has exceeded rate limits.

        Args:
            event_type: Type of event ('verification_email' or 'reset_email')

        Returns:
            tuple: (allowed: bool, retry_after_seconds: int)
        """
        ip = SecurityService._get_client_ip()
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Count events from this IP in last hour
        count = SecurityEvent.query.filter(
            SecurityEvent.ip_address == ip,
            SecurityEvent.event_type == event_type,
            SecurityEvent.created_at >= hour_ago
        ).count()

        if count >= SecurityService.IP_LIMIT_HOUR:
            oldest_event = SecurityEvent.query.filter(
                SecurityEvent.ip_address == ip,
                SecurityEvent.event_type == event_type,
                SecurityEvent.created_at >= hour_ago
            ).order_by(SecurityEvent.created_at.asc()).first()

            if oldest_event:
                retry_after = int((oldest_event.created_at + timedelta(hours=1) - now).total_seconds())
                return False, max(retry_after, 60)  # Minimum 60 seconds

            return False, 3600  # Default to 1 hour

        return True, 0

    @staticmethod
    def log_security_event(email, event_type):
        """
        Log a security event for rate limiting.

        Args:
            email: Email address involved in the event
            event_type: Type of event ('verification_email', 'reset_email', etc.)
        """
        event = SecurityEvent(
            email=email,
            ip_address=SecurityService._get_client_ip(),
            event_type=event_type
        )
        db.session.add(event)
        db.session.commit()

    @staticmethod
    def cleanup_old_events(days=7):
        """
        Clean up security events older than specified days.
        Should be run periodically (e.g., daily cron job).

        Args:
            days: Number of days to keep events (default: 7)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = SecurityEvent.query.filter(
            SecurityEvent.created_at < cutoff_date
        ).delete()
        db.session.commit()
        return deleted_count

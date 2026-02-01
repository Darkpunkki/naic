"""
Audit Logging Service - Security event logging for sensitive operations.
"""
import logging
from datetime import datetime
from typing import Optional
from flask import request


# Configure audit logger
audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)

# Create handler if not exists
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - AUDIT - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    audit_logger.addHandler(handler)


class AuditService:
    """
    Service for logging security-relevant events.
    """

    @staticmethod
    def _get_client_ip() -> str:
        """Get client IP address, handling proxies."""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr or 'unknown'

    @staticmethod
    def log_login_success(user_id: int, username: str):
        """Log successful login."""
        ip = AuditService._get_client_ip()
        audit_logger.info(
            f"LOGIN_SUCCESS | user_id={user_id} | username={username} | ip={ip}"
        )

    @staticmethod
    def log_login_failure(username: str, reason: str = "invalid_credentials"):
        """Log failed login attempt."""
        ip = AuditService._get_client_ip()
        audit_logger.warning(
            f"LOGIN_FAILURE | username={username} | reason={reason} | ip={ip}"
        )

    @staticmethod
    def log_account_locked(user_id: int, username: str, attempts: int):
        """Log account lockout."""
        ip = AuditService._get_client_ip()
        audit_logger.warning(
            f"ACCOUNT_LOCKED | user_id={user_id} | username={username} | attempts={attempts} | ip={ip}"
        )

    @staticmethod
    def log_registration(user_id: int, username: str):
        """Log new user registration."""
        ip = AuditService._get_client_ip()
        audit_logger.info(
            f"REGISTRATION | user_id={user_id} | username={username} | ip={ip}"
        )

    @staticmethod
    def log_account_deletion(user_id: int, username: str):
        """Log account deletion."""
        ip = AuditService._get_client_ip()
        audit_logger.info(
            f"ACCOUNT_DELETED | user_id={user_id} | username={username} | ip={ip}"
        )

    @staticmethod
    def log_password_change(user_id: int, username: str):
        """Log password change."""
        ip = AuditService._get_client_ip()
        audit_logger.info(
            f"PASSWORD_CHANGED | user_id={user_id} | username={username} | ip={ip}"
        )

    @staticmethod
    def log_group_membership_change(
        user_id: int,
        username: str,
        group_id: int,
        group_name: str,
        action: str  # 'joined', 'left', 'removed', 'role_changed'
    ):
        """Log group membership changes."""
        ip = AuditService._get_client_ip()
        audit_logger.info(
            f"GROUP_MEMBERSHIP | user_id={user_id} | username={username} | "
            f"group_id={group_id} | group_name={group_name} | action={action} | ip={ip}"
        )

    @staticmethod
    def log_authorization_failure(
        user_id: Optional[int],
        resource: str,
        resource_id: Optional[int],
        action: str
    ):
        """Log authorization failures (IDOR attempts)."""
        ip = AuditService._get_client_ip()
        audit_logger.warning(
            f"AUTH_FAILURE | user_id={user_id} | resource={resource} | "
            f"resource_id={resource_id} | action={action} | ip={ip}"
        )

    @staticmethod
    def log_rate_limit_exceeded(
        user_id: Optional[int],
        endpoint: str,
        limit_type: str
    ):
        """Log rate limit violations."""
        ip = AuditService._get_client_ip()
        audit_logger.warning(
            f"RATE_LIMIT | user_id={user_id} | endpoint={endpoint} | "
            f"limit_type={limit_type} | ip={ip}"
        )

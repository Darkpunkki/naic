"""
Email service for sending verification, reset, and notification emails.
Designed to be extended for future notification types.
"""
import secrets
from datetime import datetime, timedelta
from flask import render_template, url_for, current_app
from flask_mail import Message
from html.parser import HTMLParser

from app import mail
from app.models import db


class EmailService:
    """Centralized email service for all email operations."""

    # Token configuration
    TOKEN_LENGTH = 32
    VERIFICATION_TOKEN_EXPIRY_HOURS = 24
    RESET_TOKEN_EXPIRY_HOURS = 2

    @staticmethod
    def _send_email(to, subject, body_html, body_text=None):
        """
        Internal method to send email.
        All public methods should call this.

        Args:
            to: Recipient email address
            subject: Email subject line
            body_html: HTML body content
            body_text: Plain text body (auto-generated if not provided)

        Returns:
            bool: True if sent successfully, False otherwise
        """
        msg = Message(
            subject=subject,
            recipients=[to],
            html=body_html,
            body=body_text or EmailService._strip_html_tags(body_html)
        )

        try:
            mail.send(msg)
            current_app.logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to}: {e}")
            return False

    @staticmethod
    def _strip_html_tags(html):
        """Simple HTML to text conversion for email body fallback."""
        class MLStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.reset()
                self.fed = []

            def handle_data(self, d):
                self.fed.append(d)

            def get_data(self):
                return ''.join(self.fed)

        s = MLStripper()
        s.feed(html)
        return s.get_data()

    @staticmethod
    def generate_token():
        """Generate a secure random token."""
        return secrets.token_urlsafe(EmailService.TOKEN_LENGTH)

    # ==================== EMAIL VERIFICATION ====================

    @staticmethod
    def send_verification_email(user):
        """
        Send email verification link to user.

        Args:
            user: User object

        Returns:
            bool: True if sent successfully
        """
        # Generate token
        token = EmailService.generate_token()
        user.verification_token = token
        user.verification_token_expires = datetime.utcnow() + timedelta(
            hours=EmailService.VERIFICATION_TOKEN_EXPIRY_HOURS
        )
        db.session.commit()

        # Create verification URL
        verification_url = url_for(
            'auth.verify_email',
            token=token,
            _external=True
        )

        # Render email template
        html = render_template(
            'emails/verify_email.html',
            username=user.username,
            verification_url=verification_url,
            expiry_hours=EmailService.VERIFICATION_TOKEN_EXPIRY_HOURS
        )

        return EmailService._send_email(
            to=user.email,
            subject='Verify Your Email - NAIC Workout App',
            body_html=html
        )

    # ==================== PASSWORD RESET ====================

    @staticmethod
    def send_password_reset_email(user):
        """
        Send password reset link to user.

        Args:
            user: User object

        Returns:
            bool: True if sent successfully
        """
        # Generate token
        token = EmailService.generate_token()
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(
            hours=EmailService.RESET_TOKEN_EXPIRY_HOURS
        )
        db.session.commit()

        # Create reset URL
        reset_url = url_for(
            'auth.reset_password',
            token=token,
            _external=True
        )

        # Render email template
        html = render_template(
            'emails/reset_password.html',
            username=user.username,
            reset_url=reset_url,
            expiry_hours=EmailService.RESET_TOKEN_EXPIRY_HOURS
        )

        return EmailService._send_email(
            to=user.email,
            subject='Reset Your Password - NAIC Workout App',
            body_html=html
        )

    @staticmethod
    def send_password_changed_notification(user):
        """
        Alert user that their password was changed.
        Security notification - always send even if user initiated it.

        Args:
            user: User object

        Returns:
            bool: True if sent successfully
        """
        html = render_template(
            'emails/password_changed.html',
            username=user.username,
            timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
            support_email=current_app.config.get('MAIL_DEFAULT_SENDER', 'support@example.com')
        )

        return EmailService._send_email(
            to=user.email,
            subject='Security Alert: Password Changed - NAIC',
            body_html=html
        )

    # ==================== FUTURE: NOTIFICATIONS ====================

    @staticmethod
    def send_workout_reminder(user, workout):
        """
        Send workout reminder (future feature).

        Args:
            user: User object
            workout: Workout object

        Returns:
            bool: True if sent successfully
        """
        html = render_template(
            'emails/workout_reminder.html',
            username=user.username,
            workout=workout
        )

        return EmailService._send_email(
            to=user.email,
            subject=f'Reminder: {workout.workout_name} Today',
            body_html=html
        )

    @staticmethod
    def send_group_activity_notification(user, activity_summary):
        """
        Send group activity digest (future feature).

        Args:
            user: User object
            activity_summary: List of recent activities

        Returns:
            bool: True if sent successfully
        """
        html = render_template(
            'emails/group_activity.html',
            username=user.username,
            activities=activity_summary
        )

        return EmailService._send_email(
            to=user.email,
            subject='New Activity in Your Groups',
            body_html=html
        )

    @staticmethod
    def send_weekly_summary(user, stats):
        """
        Send weekly progress summary (future feature).

        Args:
            user: User object
            stats: Dictionary of workout statistics

        Returns:
            bool: True if sent successfully
        """
        html = render_template(
            'emails/weekly_summary.html',
            username=user.username,
            stats=stats
        )

        return EmailService._send_email(
            to=user.email,
            subject='Your Weekly Workout Summary',
            body_html=html
        )

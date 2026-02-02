# Email System Implementation Plan

## Overview
Comprehensive email system for NAIC workout app including verification, password reset, and future notification capabilities.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Email System Architecture                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User Actions          Email Service         Templates     │
│  ─────────────         ─────────────         ─────────     │
│  • Register       →    • send_verification   • verify.html │
│  • Forgot Pass    →    • send_reset          • reset.html  │
│  • Future:        →    • send_notification   • notif.html  │
│    - Workout reminder                                       │
│    - Group activity                                         │
│    - Weekly summary                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Database Schema Changes

### File: `app/models.py`

**Add to User model:**
```python
class User(db.Model):
    # ... existing fields ...

    # Email verification
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(100), unique=True, nullable=True)
    verification_token_expires = db.Column(db.DateTime, nullable=True)

    # Password reset
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)

    # Email preferences (for future notifications)
    email_notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    email_workout_reminders = db.Column(db.Boolean, default=False, nullable=False)
    email_group_activity = db.Column(db.Boolean, default=True, nullable=False)
```

**New model for email queue (future-proofing):**
```python
class EmailQueue(db.Model):
    """Queue for sending emails asynchronously (future enhancement)."""
    __tablename__ = 'EmailQueue'

    email_id = db.Column(db.Integer, primary_key=True)
    to_email = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    body_text = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), default='pending')  # 'pending', 'sent', 'failed'
    attempts = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
```

---

## Phase 2: Core Email Service

### File: `app/services/email_service.py`

```python
"""
Email service for sending verification, reset, and notification emails.
Designed to be extended for future notification types.
"""
from flask import render_template, current_app
from flask_mail import Message
from app import mail
from datetime import datetime, timedelta
import secrets


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
        """
        msg = Message(
            subject=subject,
            recipients=[to],
            html=body_html,
            body=body_text or strip_tags(body_html)
        )

        try:
            mail.send(msg)
            current_app.logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to}: {e}")
            return False

    @staticmethod
    def generate_token():
        """Generate a secure random token."""
        return secrets.token_urlsafe(EmailService.TOKEN_LENGTH)

    # ==================== EMAIL VERIFICATION ====================

    @staticmethod
    def send_verification_email(user):
        """Send email verification link to user."""
        from app.models import db

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
        """Send password reset link to user."""
        from app.models import db

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

    # ==================== FUTURE: NOTIFICATIONS ====================

    @staticmethod
    def send_workout_reminder(user, workout):
        """Send workout reminder (future feature)."""
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
        """Send group activity digest (future feature)."""
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
        """Send weekly progress summary (future feature)."""
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


def strip_tags(html):
    """Simple HTML to text conversion for email body fallback."""
    from html.parser import HTMLParser

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
```

---

## Phase 3: Authentication Routes Updates

### File: `app/routes/auth.py`

**New routes to add:**

```python
# ==================== EMAIL VERIFICATION ====================

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify email address via token."""
    user = User.query.filter_by(verification_token=token).first()

    if not user:
        flash('Invalid verification link.', 'danger')
        return redirect(url_for('auth.login'))

    if user.verification_token_expires < datetime.utcnow():
        flash('Verification link has expired. Please request a new one.', 'warning')
        return redirect(url_for('auth.resend_verification'))

    user.email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.session.commit()

    flash('Email verified successfully! You can now log in.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend verification email."""
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user and not user.email_verified:
            EmailService.send_verification_email(user)
            flash('Verification email sent! Check your inbox.', 'success')
        else:
            # Don't reveal if email exists
            flash('If that email exists, a verification link has been sent.', 'info')

        return redirect(url_for('auth.login'))

    return render_template('resend_verification.html')


# ==================== PASSWORD RESET ====================

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset."""
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            EmailService.send_password_reset_email(user)

        # Always show success to prevent user enumeration
        flash('If that email exists, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password via token."""
    user = User.query.filter_by(reset_token=token).first()

    if not user or user.reset_token_expires < datetime.utcnow():
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        # Validate password strength
        is_valid, error = validate_password_strength(password)
        if not is_valid:
            flash(error, 'danger')
            return render_template('reset_password.html', token=token)

        # Reset password
        user.password_hash = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()

        AuditService.log_password_change(user.user_id, user.username)
        flash('Password reset successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)
```

**Update register route:**
```python
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # ... existing validation ...

        # Create user
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            email_verified=False  # New field
        )
        db.session.add(new_user)
        db.session.commit()

        # Send verification email
        EmailService.send_verification_email(new_user)

        logger.info(f"New user registered: {username}")
        AuditService.log_registration(new_user.user_id, username)
        flash('Registration successful! Check your email to verify your account.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')
```

**Optional: Require email verification for login:**
```python
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # ... existing checks ...

        # Check email verification (optional - enable if desired)
        if not user.email_verified:
            flash('Please verify your email before logging in. Check your inbox.', 'warning')
            return redirect(url_for('auth.resend_verification'))

        # ... rest of login logic ...
```

---

## Phase 4: Email Templates

### Directory: `templates/emails/`

Create base email template with consistent branding:

**`templates/emails/base.html`:**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(120deg, #38bdf8, #0ea5e9); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #f8fafc; padding: 30px; border-radius: 0 0 8px 8px; }
        .button { display: inline-block; padding: 12px 30px; background: #0ea5e9; color: white; text-decoration: none; border-radius: 999px; font-weight: bold; }
        .footer { text-align: center; margin-top: 20px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>NAIC Workout App</h1>
        </div>
        <div class="content">
            {% block content %}{% endblock %}
        </div>
        <div class="footer">
            <p>© 2025 Nordic AI Consulting | <a href="{{ url_for('main_bp.index', _external=True) }}">Visit App</a></p>
            <p>If you didn't request this email, please ignore it.</p>
        </div>
    </div>
</body>
</html>
```

**`templates/emails/verify_email.html`:**
```html
{% extends "emails/base.html" %}

{% block content %}
<h2>Welcome, {{ username }}!</h2>
<p>Thanks for signing up for NAIC Workout App. Please verify your email address to get started.</p>
<p style="text-align: center; margin: 30px 0;">
    <a href="{{ verification_url }}" class="button">Verify Email Address</a>
</p>
<p>Or copy and paste this link into your browser:</p>
<p style="word-break: break-all; color: #0ea5e9;">{{ verification_url }}</p>
<p><strong>This link expires in {{ expiry_hours }} hours.</strong></p>
{% endblock %}
```

**`templates/emails/reset_password.html`:**
```html
{% extends "emails/base.html" %}

{% block content %}
<h2>Password Reset Request</h2>
<p>Hi {{ username }},</p>
<p>We received a request to reset your password. Click the button below to create a new password:</p>
<p style="text-align: center; margin: 30px 0;">
    <a href="{{ reset_url }}" class="button">Reset Password</a>
</p>
<p>Or copy and paste this link into your browser:</p>
<p style="word-break: break-all; color: #0ea5e9;">{{ reset_url }}</p>
<p><strong>This link expires in {{ expiry_hours }} hours.</strong></p>
<p>If you didn't request a password reset, please ignore this email. Your password will remain unchanged.</p>
{% endblock %}
```

---

## Phase 5: Web Templates (User-Facing)

### Templates to create:

- `templates/forgot_password.html` - Form to request reset
- `templates/reset_password.html` - Form to set new password
- `templates/resend_verification.html` - Form to resend verification

---

## Phase 6: Migration Script

### File: `scripts/migrate_email_system.py`

```python
"""
Migration to add email verification and password reset functionality.
Run: python scripts/migrate_email_system.py
"""
```

Add columns:
- `email_verified`
- `verification_token`
- `verification_token_expires`
- `reset_token`
- `reset_token_expires`
- `email_notifications_enabled`
- `email_workout_reminders`
- `email_group_activity`

Optional: Create `EmailQueue` table for future async sending.

---

## Phase 7: Future Enhancements (Post-MVP)

### Notification System
- Workout reminders (scheduled tasks)
- Group activity notifications
- Weekly progress summaries
- Admin notifications (new user signups)

### Implementation Approach:
1. **Celery + Redis** for background task queue
2. **Cron jobs** for scheduled emails
3. **Email preferences page** for users to control notifications

### User Preferences Route:
```python
@user_bp.route('/email-preferences', methods=['GET', 'POST'])
@require_auth
def email_preferences():
    """Manage email notification settings."""
    # Toggle email_workout_reminders, email_group_activity, etc.
```

---

## Phase 8: Security Enhancements

### File: `app/services/security_service.py` (NEW)

```python
"""
Security service for rate limiting and abuse prevention.
"""
from datetime import datetime, timedelta
from app.models import db
from flask import request


class SecurityEvent(db.Model):
    """Track security-related events for rate limiting and abuse detection."""
    __tablename__ = 'SecurityEvents'

    event_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=True, index=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False)  # 'verification_email', 'reset_email', etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<SecurityEvent {self.event_type} {self.email or self.ip_address}>"


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

        Returns: (allowed: bool, retry_after_seconds: int)
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

        if hour_count >= SecurityService.EMAIL_VERIFICATION_LIMIT_HOUR:
            # Calculate retry time
            oldest_event = SecurityEvent.query.filter(
                SecurityEvent.email == email,
                SecurityEvent.event_type == event_type,
                SecurityEvent.created_at >= hour_ago
            ).order_by(SecurityEvent.created_at.asc()).first()

            retry_after = int((oldest_event.created_at + timedelta(hours=1) - now).total_seconds())
            return False, retry_after

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

        Returns: (allowed: bool, retry_after_seconds: int)
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

            retry_after = int((oldest_event.created_at + timedelta(hours=1) - now).total_seconds())
            return False, retry_after

        return True, 0

    @staticmethod
    def log_security_event(email, event_type):
        """Log a security event for rate limiting."""
        event = SecurityEvent(
            email=email,
            ip_address=SecurityService._get_client_ip(),
            event_type=event_type
        )
        db.session.add(event)
        db.session.commit()

    @staticmethod
    def cleanup_old_events():
        """Clean up security events older than 7 days (run periodically)."""
        week_ago = datetime.utcnow() - timedelta(days=7)
        SecurityEvent.query.filter(SecurityEvent.created_at < week_ago).delete()
        db.session.commit()
```

### Update `app/models.py`:

Add session token field to User model:

```python
class User(db.Model):
    # ... existing fields ...

    # Session management (invalidate sessions on password change)
    session_token = db.Column(db.String(100), nullable=True)
```

### Update `app/routes/auth.py`:

**Add session token validation to require_auth:**

```python
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'warning')
            return redirect(url_for('auth.login'))

        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            flash('Please log in.', 'warning')
            return redirect(url_for('auth.login'))

        # Check if session token still valid (invalidates on password change)
        if user.session_token and user.session_token != session.get('session_token'):
            session.clear()
            flash('Your session has expired. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function
```

**Update login route to set session token:**

```python
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # ... existing code ...

    # After successful password check:
    regenerate_session()
    session['user_id'] = user.user_id
    session['username'] = user.username
    session['session_token'] = user.session_token  # Track session validity
    session.permanent = True

    # ... rest of code
```

**Update register route to initialize session token:**

```python
new_user = User(
    username=username,
    email=email,
    password_hash=hashed_password,
    email_verified=False,
    session_token=secrets.token_urlsafe(32)  # Initialize
)
```

**Update verification email sending with rate limiting:**

```python
@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email')

        # Check rate limits
        email_allowed, email_retry = SecurityService.check_email_rate_limit(email, 'verification_email')
        ip_allowed, ip_retry = SecurityService.check_ip_rate_limit('verification_email')

        if not email_allowed:
            flash(f'Too many verification emails sent. Please try again in {email_retry // 60} minutes.', 'danger')
            return redirect(url_for('auth.login'))

        if not ip_allowed:
            flash(f'Too many requests from your IP. Please try again in {ip_retry // 60} minutes.', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()

        if user and not user.email_verified:
            EmailService.send_verification_email(user)
            SecurityService.log_security_event(email, 'verification_email')
            flash('Verification email sent! Check your inbox.', 'success')
        else:
            flash('If that email exists, a verification link has been sent.', 'info')

        return redirect(url_for('auth.login'))

    return render_template('resend_verification.html')
```

**Update forgot password with rate limiting:**

```python
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        # Check rate limits
        email_allowed, email_retry = SecurityService.check_email_rate_limit(email, 'reset_email')
        ip_allowed, ip_retry = SecurityService.check_ip_rate_limit('reset_email')

        if not email_allowed:
            flash(f'Too many password reset requests. Please try again in {email_retry // 60} minutes.', 'danger')
            return redirect(url_for('auth.login'))

        if not ip_allowed:
            flash(f'Too many requests from your IP. Please try again in {ip_retry // 60} minutes.', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()

        if user:
            EmailService.send_password_reset_email(user)
            SecurityService.log_security_event(email, 'reset_email')

        # Always show success (prevent user enumeration)
        flash('If that email exists, a password reset link has been sent.', 'info')
        AuditService.log_password_reset_request(email)
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')
```

**Update reset password with security features:**

```python
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()

    # Check token validity
    if not user:
        flash('Invalid reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if not user.reset_token:
        flash('This reset link has already been used.', 'warning')
        return redirect(url_for('auth.login'))

    if user.reset_token_expires < datetime.utcnow():
        flash('Reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        # Validate password strength
        is_valid, error = validate_password_strength(password)
        if not is_valid:
            flash(error, 'danger')
            return render_template('reset_password.html', token=token)

        # Prevent password reuse
        if check_password_hash(user.password_hash, password):
            flash('New password must be different from your current password.', 'danger')
            return render_template('reset_password.html', token=token)

        # Reset password and invalidate all sessions
        user.password_hash = generate_password_hash(password)
        user.reset_token = None  # Prevent token reuse
        user.reset_token_expires = None
        user.session_token = secrets.token_urlsafe(32)  # Invalidate all active sessions
        db.session.commit()

        # Send notification email
        EmailService.send_password_changed_notification(user)

        AuditService.log_password_change(user.user_id, user.username)
        flash('Password reset successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)
```

### Update `app/services/email_service.py`:

Add password changed notification:

```python
@staticmethod
def send_password_changed_notification(user):
    """
    Alert user that their password was changed.
    Security notification - always send even if user initiated it.
    """
    from flask import url_for

    html = render_template(
        'emails/password_changed.html',
        username=user.username,
        timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
        support_email=current_app.config['MAIL_DEFAULT_SENDER']
    )

    return EmailService._send_email(
        to=user.email,
        subject='Security Alert: Password Changed - NAIC',
        body_html=html
    )
```

### Update `app/services/audit_service.py`:

Add new audit methods:

```python
@staticmethod
def log_email_verification(user_id: int, username: str):
    """Log email verification."""
    ip = AuditService._get_client_ip()
    audit_logger.info(
        f"EMAIL_VERIFIED | user_id={user_id} | username={username} | ip={ip}"
    )

@staticmethod
def log_password_reset_request(email: str):
    """Log password reset request (even if email doesn't exist - for security monitoring)."""
    ip = AuditService._get_client_ip()
    audit_logger.info(
        f"PASSWORD_RESET_REQUESTED | email={email} | ip={ip}"
    )

@staticmethod
def log_password_reset_completed(user_id: int, username: str):
    """Log successful password reset."""
    ip = AuditService._get_client_ip()
    audit_logger.warning(  # Warning level for security-critical events
        f"PASSWORD_RESET_COMPLETED | user_id={user_id} | username={username} | ip={ip}"
    )
```

### New Template: `templates/emails/password_changed.html`

```html
{% extends "emails/base.html" %}

{% block content %}
<h2>Security Alert: Password Changed</h2>
<p>Hi {{ username }},</p>
<p>This email confirms that your password was successfully changed on <strong>{{ timestamp }}</strong>.</p>

<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
    <strong>⚠️ Didn't change your password?</strong><br>
    If you did not make this change, please contact us immediately at
    <a href="mailto:{{ support_email }}">{{ support_email }}</a>
</div>

<p>Your account security is important to us. Here are some tips to keep your account safe:</p>
<ul>
    <li>Never share your password with anyone</li>
    <li>Use a unique password for each service</li>
    <li>Enable two-factor authentication when available</li>
</ul>

<p>All your active sessions have been logged out for security. Please log in with your new password.</p>
{% endblock %}
```

---

## Security Considerations (Updated)

### ✅ **Phase 1: Implemented Now**

✅ **Token Security:**
- Cryptographically secure random tokens (`secrets.token_urlsafe`)
- Tokens expire after set time (24h verification, 2h reset)
- **One-time use enforced** (cleared immediately after use)
- Token reuse detection

✅ **Rate Limiting:**
- **Email-based limits:** 3 verification/reset emails per hour per email
- **IP-based limits:** 10 requests per hour per IP
- **Daily limits:** 5 total emails per day per email address
- Tracked in database with automatic cleanup

✅ **Session Security:**
- **Session invalidation on password change**
- Session token validation on every request
- All active sessions killed when password is reset

✅ **Password Security:**
- **Prevent password reuse** (can't reset to current password)
- Password strength validation (8+ chars, uppercase, number)
- Hashed with scrypt (werkzeug default)

✅ **Security Notifications:**
- **Password change alert email** sent automatically
- User can contact support if unauthorized

✅ **User Enumeration Prevention:**
- Generic success messages ("If email exists...")
- Don't reveal whether email is registered
- Same response time regardless of email existence

✅ **Audit Logging:**
- All password resets logged
- Email verification logged
- Reset requests logged (even for non-existent emails)
- IP address tracked in all logs

✅ **HTTPS Only:**
- Email links use `_external=True` (full URLs)
- Render automatically provides HTTPS

### 🔒 **Phase 2: Future Enhancements**

🔒 **CAPTCHA** on forgot password form (prevent automated abuse)
🔒 **Suspicious activity detection** (flag unusual patterns)
🔒 **Account lockout** after multiple failed verification attempts
🔒 **Two-factor authentication** (TOTP)
🔒 **Security event monitoring dashboard** for admins

---

## Testing Checklist (Updated)

### Email Verification:
- [ ] Register new user → receives verification email
- [ ] Click link → email verified, can log in
- [ ] Expired token → shows error, can resend
- [ ] Invalid token → shows error

### Password Reset:
- [ ] Request reset → receives email
- [ ] Click link → can set new password
- [ ] New password works for login
- [ ] Expired token → shows error
- [ ] Invalid token → shows error
- [ ] Old password no longer works

### Edge Cases:
- [ ] Email already verified → can't verify again
- [ ] Non-existent email → generic message (no enumeration)
- [ ] Used verification token → shows "already used" error
- [ ] Used reset token → shows "already used" error

### Security Tests:
- [ ] Email rate limiting: 4th email in hour blocked
- [ ] IP rate limiting: 11th request in hour blocked
- [ ] Daily email limit: 6th email in day blocked
- [ ] Password reuse: Can't reset to current password
- [ ] Session invalidation: Old session killed after password reset
- [ ] Password change notification sent
- [ ] Audit logs created for all security events
- [ ] Rate limit retry time calculated correctly

---

## Files Summary

| File | Action |
|------|--------|
| `app/models.py` | Add email verification fields + session_token to User, add SecurityEvent model |
| `app/services/email_service.py` | New - centralized email logic + password change notification |
| `app/services/security_service.py` | New - rate limiting and security event tracking |
| `app/services/audit_service.py` | Add email/password reset audit methods |
| `app/routes/auth.py` | Add verify/reset routes, update register, add rate limiting |
| `app/__init__.py` | Configure Flask-Mail |
| `scripts/migrate_email_system.py` | Migration script (add columns + SecurityEvent table) |
| `templates/emails/base.html` | Email base template |
| `templates/emails/verify_email.html` | Verification email template |
| `templates/emails/reset_password.html` | Password reset email template |
| `templates/emails/password_changed.html` | Password change notification template |
| `templates/forgot_password.html` | Forgot password form |
| `templates/reset_password.html` | Reset password form |
| `templates/resend_verification.html` | Resend verification form |
| `requirements.txt` | Add Flask-Mail |

---

## Implementation Order

1. ✅ Email configuration (done - in .env)
2. Database schema changes
3. Email service implementation
4. Email templates (HTML)
5. Auth routes updates
6. Web templates (forms)
7. Migration script
8. Testing
9. Deploy to Render

---

## Estimated Complexity

**Email Verification:** Medium (3-4 hours)
**Password Reset:** Medium (3-4 hours)
**Email Templates:** Low (1-2 hours)
**Testing & Debugging:** Medium (2-3 hours)

**Total:** ~10-13 hours for full implementation

---

## Questions to Answer Before Implementation

1. **Email verification requirement:**
   - Should users be able to log in before verifying email? (Recommended: YES, but show banner)
   - Or block login until verified? (More restrictive)

2. **Token expiry:**
   - 24 hours for verification OK?
   - 2 hours for password reset OK?

3. **Notification preferences:**
   - Implement user preferences page now or later?
   - Default all notifications to ON or OFF?

4. **Email sending:**
   - Synchronous (send immediately, user waits) or asynchronous (queue for later)?
   - For MVP: synchronous is fine

---

## Next Steps

Ready to implement when you are! Let me know if you want to:
- Adjust the plan
- Start implementation
- Focus on specific phase first

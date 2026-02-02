import logging
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User, db
from app.services.audit_service import AuditService
from app.services.email_service import EmailService
from app.services.security_service import SecurityService

logger = logging.getLogger(__name__)


def require_auth(f):
    """Decorator that requires a logged-in user with valid session."""
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


def require_admin(f):
    """Decorator that requires an authenticated admin user."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'warning')
            return redirect(url_for('auth.login'))

        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('main_bp.index'))

        return f(*args, **kwargs)
    return decorated_function

auth_bp = Blueprint("auth", __name__)


def validate_password_strength(password):
    """
    Validate password strength:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one number
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number."
    return True, None


def check_account_lockout(user):
    """
    Check if account is locked due to failed login attempts.
    Returns (is_locked, message)
    """
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining_minutes = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        return True, f"Account temporarily locked. Try again in {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}."
    return False, None


def record_failed_login(user):
    """
    Record a failed login attempt and lock account if threshold exceeded.
    """
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

    # Lock account after 5 failed attempts for 15 minutes
    if user.failed_login_attempts >= 5:
        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        logger.warning(f"Account locked for user {user.username} due to {user.failed_login_attempts} failed attempts")
        AuditService.log_account_locked(user.user_id, user.username, user.failed_login_attempts)

    db.session.commit()


def reset_failed_login_attempts(user):
    """
    Reset failed login counter after successful login.
    """
    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.commit()


def regenerate_session():
    """
    Regenerate session ID to prevent session fixation attacks.
    Preserves session data while getting a new session ID.
    """
    # Store existing session data
    session_data = dict(session)
    # Clear and regenerate
    session.clear()
    # Restore data with new session ID
    session.update(session_data)
    session.modified = True


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Import limiter from app to apply rate limiting
    from app import limiter

    if request.method == 'POST':
        # Rate limit: 3 registrations per minute, 10 per hour per IP
        try:
            limiter.check()
        except Exception:
            pass  # Continue even if limiter fails

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not email or not confirm_password:
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.register'))

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))

        # Validate password strength
        is_valid, error_message = validate_password_strength(password)
        if not is_valid:
            flash(error_message, 'error')
            return redirect(url_for('auth.register'))

        # Check if the username is taken
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'error')
            return redirect(url_for('auth.register'))

        # Check if the email is taken
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already in use.', 'error')
            return redirect(url_for('auth.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            email_verified=False,
            session_token=secrets.token_urlsafe(32)
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


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if not user:
            # Generic message to avoid user enumeration
            AuditService.log_login_failure(username, "user_not_found")
            flash('Invalid username or password.', 'error')
            return redirect(url_for('auth.login'))

        # Check if account is locked
        is_locked, lock_message = check_account_lockout(user)
        if is_locked:
            flash(lock_message, 'error')
            return redirect(url_for('auth.login'))

        # Check password
        if not check_password_hash(user.password_hash, password):
            record_failed_login(user)
            AuditService.log_login_failure(username, "invalid_password")
            flash('Invalid username or password.', 'error')
            return redirect(url_for('auth.login'))

        # Successful login - reset failed attempts and regenerate session
        reset_failed_login_attempts(user)

        # Regenerate session ID to prevent session fixation
        regenerate_session()

        session['user_id'] = user.user_id
        session['username'] = user.username
        session['session_token'] = user.session_token  # Track session validity
        session.permanent = True  # Use PERMANENT_SESSION_LIFETIME

        logger.info(f"User logged in: {username}")
        AuditService.log_login_success(user.user_id, username)

        # Show banner if email not verified (but allow login)
        if not user.email_verified:
            flash('Logged in successfully. Please verify your email address.', 'warning')
        else:
            flash('Logged in successfully.', 'success')

        return redirect(url_for('main_bp.index'))

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"User logged out: {username}")
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


# ==================== EMAIL VERIFICATION ====================

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify email address via token."""
    user = User.query.filter_by(verification_token=token).first()

    if not user:
        flash('Invalid verification link.', 'danger')
        return redirect(url_for('auth.login'))

    if not user.verification_token:
        flash('This verification link has already been used.', 'warning')
        return redirect(url_for('auth.login'))

    if user.verification_token_expires < datetime.utcnow():
        flash('Verification link has expired. Please request a new one.', 'warning')
        return redirect(url_for('auth.resend_verification'))

    user.email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.session.commit()

    AuditService.log_email_verification(user.user_id, user.username)
    flash('Email verified successfully! You can now log in.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend verification email."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('resend_verification.html')

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
            # Don't reveal if email exists or is already verified
            flash('If that email exists and is unverified, a verification link has been sent.', 'info')

        return redirect(url_for('auth.login'))

    return render_template('resend_verification.html')


# ==================== PASSWORD RESET ====================

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('forgot_password.html')

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

        # Always show success message to prevent user enumeration
        flash('If that email exists, a password reset link has been sent.', 'info')
        AuditService.log_password_reset_request(email)
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password via token."""
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
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

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

        AuditService.log_password_reset_completed(user.user_id, user.username)
        flash('Password reset successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)


@auth_bp.route('/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change password for logged-in user."""
    user = User.query.get(session['user_id'])

    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Verify current password
    if not check_password_hash(user.password_hash, current_password):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('main_bp.index'))

    # Check passwords match
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('main_bp.index'))

    # Validate password strength
    is_valid, error = validate_password_strength(new_password)
    if not is_valid:
        flash(error, 'danger')
        return redirect(url_for('main_bp.index'))

    # Prevent password reuse
    if check_password_hash(user.password_hash, new_password):
        flash('New password must be different from your current password.', 'danger')
        return redirect(url_for('main_bp.index'))

    # Update password and invalidate all sessions
    user.password_hash = generate_password_hash(new_password)
    old_session_token = user.session_token
    user.session_token = secrets.token_urlsafe(32)  # Generate new session token
    db.session.commit()

    # Update current session with new token
    session['session_token'] = user.session_token

    # Send notification email
    EmailService.send_password_changed_notification(user)

    AuditService.log_password_change(user.user_id, user.username)
    flash('Password changed successfully! All other sessions have been logged out.', 'success')
    return redirect(url_for('main_bp.index'))

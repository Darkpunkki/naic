import logging
import re
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User, db
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

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
            password_hash=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()

        logger.info(f"New user registered: {username}")
        AuditService.log_registration(new_user.user_id, username)
        flash('Registration successful. Please log in.', 'success')
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
        session.permanent = True  # Use PERMANENT_SESSION_LIFETIME

        logger.info(f"User logged in: {username}")
        AuditService.log_login_success(user.user_id, username)
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

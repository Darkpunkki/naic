"""
Decorators - Authentication and rate limiting decorators.
"""
from functools import wraps
from flask import session, redirect, url_for, flash, jsonify, request

from app.guards.rate_limiter import RateLimiter, RateLimitExceeded


def require_auth(f):
    """
    Decorator that requires user to be logged in.

    Redirects to login page for HTML requests, returns 401 for JSON requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Check if this is an API/JSON request
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Unauthorized access'}), 401
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def rate_limit_llm(f):
    """
    Decorator that enforces rate limiting for LLM API calls.

    Must be used after @require_auth since it needs user_id in session.

    Limits:
    - 10 requests per hour
    - 30 requests per day
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            # Should not happen if @require_auth is used first
            if request.is_json:
                return jsonify({'error': 'Unauthorized access'}), 401
            return redirect(url_for('auth.login'))

        try:
            RateLimiter.check_and_increment(user_id)
        except RateLimitExceeded as e:
            if request.is_json:
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': e.message,
                    'limit_type': e.limit_type,
                    'reset_time': e.reset_time.isoformat()
                }), 429
            flash(e.message, 'error')
            return redirect(request.referrer or url_for('main_bp.index'))

        return f(*args, **kwargs)
    return decorated_function

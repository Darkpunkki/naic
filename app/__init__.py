import logging
import os
from datetime import timedelta

import nltk
from flask import Flask, request
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.models import db

# Initialize CSRF protection
csrf = CSRFProtect()

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://"
)

from app.routes.auth import auth_bp
from app.routes.workouts import workouts_bp
from app.routes.leaderboard import leaderboard_bp
from app.routes.main import main_bp
from app.routes.stats import stats_bp
from app.routes.user import user_bp
from app.routes.groups import groups_bp
from app.routes.admin import admin_bp

from scripts.init_db import init_db


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass


def _validate_environment(app, test_config=None):
    """Validate required environment variables on startup."""
    if test_config and test_config.get("TESTING"):
        return  # Skip validation in test mode

    errors = []

    # SECRET_KEY is required (no default allowed)
    if not os.getenv("SECRET_KEY"):
        errors.append("SECRET_KEY environment variable is required")

    # OPENAI_API_KEY is required for AI features
    if not os.getenv("OPENAI_API_KEY"):
        errors.append("OPENAI_API_KEY environment variable is required")

    if errors:
        raise ConfigurationError(
            "Missing required configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )


def create_app(test_config=None):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )

    # Validate environment variables before proceeding
    _validate_environment(app, test_config)

    # SECRET_KEY is required - no fallback allowed
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key and test_config:
        secret_key = test_config.get("SECRET_KEY", "test-secret-key-for-testing-only")
    app.secret_key = secret_key

    # Set ENV from environment variable
    app.config["ENV"] = os.getenv("FLASK_ENV", "development")

    if test_config:
        app.config.update(test_config)

    # Secure session configuration (HTTPS confirmed enabled)
    app.config['SESSION_COOKIE_SECURE'] = os.getenv("FLASK_ENV") == "production"  # HTTPS only in production
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access to session cookie
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Session expiry

    app.config.setdefault("IMPACT_BASE_LOAD", float(os.getenv("IMPACT_BASE_LOAD", 10)))
    app.config.setdefault("IMPACT_EXTERNAL_WEIGHT_FACTOR", float(os.getenv("IMPACT_EXTERNAL_WEIGHT_FACTOR", 1.0)))
    app.config.setdefault("IMPACT_BODYWEIGHT_FACTOR", float(os.getenv("IMPACT_BODYWEIGHT_FACTOR", 0.25)))
    app.config.setdefault("IMPACT_MIN_EFFECTIVE_LOAD", float(os.getenv("IMPACT_MIN_EFFECTIVE_LOAD", 0.0)))

    if app.config.get("ENV", "development") == "development":
        logger.info("Running in development mode.")

    if not app.config.get("TESTING") and not app.config.get("SKIP_NLTK_DOWNLOAD"):
        nltk.download("wordnet")
        nltk.download("omw-1.4")

    init_db(app)

    # Initialize CSRF protection
    csrf.init_app(app)

    # Initialize rate limiter
    limiter.init_app(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(workouts_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(admin_bp)

    # Add security headers to all responses
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Basic CSP - allows inline scripts/styles for Bootstrap compatibility
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        return response

    return app


__all__ = ["create_app", "db"]

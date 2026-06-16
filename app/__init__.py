import logging
import os
from datetime import timedelta

import nltk
from dotenv import load_dotenv
from flask import Flask, request
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate

from app.models import db


def _load_repo_dotenv_if_present():
    """Load environment variables from repo-root .env when enabled and available."""
    should_load = os.getenv("LOAD_DOTENV", "true").strip().lower() in ("true", "1", "yes", "on")
    if not should_load:
        return False

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dotenv_path = os.path.join(repo_root, ".env")
    if not os.path.isfile(dotenv_path):
        return False

    load_dotenv(dotenv_path=dotenv_path, override=False)
    return True


# Load .env before importing modules that read env vars at import time.
DOTENV_LOADED = _load_repo_dotenv_if_present()

# Use the OS trust store so HTTPS works behind TLS-inspecting proxies/antivirus.
# certifi alone can't verify their re-signed certificates ("unable to get local
# issuer certificate"); the intercepting root lives in the OS store. Must run before
# the OpenAI client is constructed (i.e. before the route/service imports below).
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:  # pragma: no cover - falls back to certifi if truststore is unavailable
    pass

# Initialize CSRF protection
csrf = CSRFProtect()

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://"
)

# Initialize Flask-Mail
mail = Mail()

# Initialize Flask-Migrate (Alembic is the schema source of truth)
migrate = Migrate()


def _apply_migrations_on_startup(app):
    """Apply Alembic migrations to head on boot for real (non-test) databases.

    Replaces the old db.create_all() bootstrap. Defensive: skips under TESTING
    (the test fixture builds its own schema), skips when migrations/ doesn't
    exist yet, and never lets a migration error crash app startup.
    """
    if app.config.get("TESTING"):
        return
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if not os.path.isdir(os.path.join(repo_root, "migrations")):
        return
    try:
        from flask_migrate import upgrade
        with app.app_context():
            upgrade()
    except Exception as exc:  # pragma: no cover - logged, never fatal on boot
        logging.getLogger(__name__).warning("Startup database migration failed: %s", exc)


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
    if DOTENV_LOADED:
        logger.info("Loaded environment variables from .env")

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

    # Email configuration (Flask-Mail)
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'mail.zoner.fi')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))

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

    # Wire Flask-Migrate (db is initialized inside init_db) and apply any pending
    # migrations on boot for real databases (no-op under TESTING / before setup).
    migrate.init_app(app, db)
    _apply_migrations_on_startup(app)

    # Initialize CSRF protection
    csrf.init_app(app)

    # Initialize rate limiter
    limiter.init_app(app)

    # Initialize Flask-Mail
    mail.init_app(app)

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


__all__ = ["create_app", "db", "mail"]

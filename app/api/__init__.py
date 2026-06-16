"""Versioned REST API for programmatic / agent access.

This is a thin transport over the existing service layer, authenticated by a
per-user bearer token (see app/services/api_token_service.py). It is separate
from the session/cookie-based HTML routes and is exempt from CSRF (it uses
``Authorization: Bearer`` rather than form posts).
"""
from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# Import routes to register handlers on the blueprint.
from app.api import routes  # noqa: E402,F401

__all__ = ["api_bp"]

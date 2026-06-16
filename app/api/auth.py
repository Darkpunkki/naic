"""Bearer-token authentication for the REST API.

The resolved user (from the token) is the *only* identity the API trusts; it is
stored on ``flask.g.current_user``. Endpoints scope every query to that user and
must never accept a user id from the request body/query.
"""
import functools

from flask import request, jsonify, g

from app.services.api_token_service import ApiTokenService


def _extract_bearer_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return None


def require_api_token(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        user = ApiTokenService.resolve_user(token) if token else None
        if user is None:
            return jsonify({
                "error": "unauthorized",
                "message": "Missing or invalid API token. Send 'Authorization: Bearer <token>'.",
            }), 401
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper

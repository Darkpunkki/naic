"""Mint, verify, and revoke per-user API tokens for programmatic/agent access.

The plaintext token is returned only once at creation; only its SHA-256 hash is
persisted. Verification resolves the owning user from a presented token, so the
REST API never has to trust a caller-supplied user id.
"""
import hashlib
import secrets
from datetime import datetime

from app.models import db, ApiToken

# Plaintext format: "naic_<43 url-safe chars>". The "naic_" label makes tokens
# recognizable; the random part carries the entropy.
_TOKEN_BYTES = 32
_TOKEN_LABEL = "naic"


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


class ApiTokenService:

    @staticmethod
    def generate(user_id: int, name: str = "agent"):
        """Create a token for a user.

        Returns ``(plaintext, ApiToken)``. The plaintext is shown only once and is
        never stored — persist/copy it now or it is unrecoverable.
        """
        plaintext = f"{_TOKEN_LABEL}_{secrets.token_urlsafe(_TOKEN_BYTES)}"
        token = ApiToken(
            user_id=user_id,
            name=(name or "agent")[:100],
            token_hash=hash_token(plaintext),
            token_prefix=plaintext[:12],
        )
        db.session.add(token)
        db.session.commit()
        return plaintext, token

    @staticmethod
    def resolve_user(plaintext: str):
        """Return the User owning an active token matching ``plaintext``, or None.

        Touches ``last_used_at`` on success.
        """
        if not plaintext:
            return None
        token = ApiToken.query.filter_by(
            token_hash=hash_token(plaintext), revoked_at=None
        ).first()
        if token is None:
            return None
        token.last_used_at = datetime.utcnow()
        db.session.commit()
        return token.user

    @staticmethod
    def list_for_user(user_id: int):
        return (
            ApiToken.query.filter_by(user_id=user_id)
            .order_by(ApiToken.created_at.desc())
            .all()
        )

    @staticmethod
    def revoke(token_id: int) -> bool:
        token = ApiToken.query.get(token_id)
        if token is None or token.revoked_at is not None:
            return False
        token.revoked_at = datetime.utcnow()
        db.session.commit()
        return True

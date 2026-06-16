"""Tests for the token-authed REST API (/api/v1)."""
from datetime import datetime

from app.models import db, User, Workout
from app.services.api_token_service import ApiTokenService, hash_token


def _user(username="api_user"):
    u = User(username=username, password_hash="x")
    db.session.add(u)
    db.session.commit()
    return u


def _workout(user_id, name):
    w = Workout(user_id=user_id, workout_name=name, workout_date=datetime.utcnow(), is_completed=False)
    db.session.add(w)
    db.session.commit()
    return w


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- token service ---

def test_generate_stores_hash_not_plaintext(app):
    user = _user()
    plaintext, tok = ApiTokenService.generate(user.user_id, name="discord")
    assert plaintext.startswith("naic_")
    assert tok.token_hash == hash_token(plaintext)
    assert tok.token_hash != plaintext
    assert tok.token_prefix == plaintext[:12]
    assert tok.name == "discord"


def test_resolve_user_and_revoke(app):
    user = _user()
    plaintext, tok = ApiTokenService.generate(user.user_id)
    resolved = ApiTokenService.resolve_user(plaintext)
    assert resolved is not None and resolved.user_id == user.user_id
    assert ApiTokenService.resolve_user("naic_wrong") is None
    assert ApiTokenService.revoke(tok.token_id) is True
    assert ApiTokenService.resolve_user(plaintext) is None  # revoked → no longer resolves


# --- endpoints ---

def test_health_no_auth(client, app):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_me_requires_token(client, app):
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers=_auth("naic_bad")).status_code == 401


def test_me_returns_token_owner(client, app):
    user = _user("owner")
    plaintext, _ = ApiTokenService.generate(user.user_id)
    resp = client.get("/api/v1/me", headers=_auth(plaintext))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user_id"] == user.user_id
    assert body["username"] == "owner"


def test_workouts_scoped_to_token_owner(client, app):
    alice = _user("alice")
    bob = _user("bob")
    _workout(alice.user_id, "A1")
    _workout(bob.user_id, "B1")
    a_token, _ = ApiTokenService.generate(alice.user_id)

    resp = client.get("/api/v1/workouts", headers=_auth(a_token))
    assert resp.status_code == 200
    names = [w["name"] for w in resp.get_json()["workouts"]]
    assert names == ["A1"]  # bob's workout is never visible to alice's token


def test_create_workout_from_plan_offline(client, app):
    user = _user("creator")
    token, _ = ApiTokenService.generate(user.user_id)
    plan = {
        "workout_name": "Agent Push Day",
        "movements": [
            {
                "name": "Bench Press",
                "sets": 2,
                "reps": 8,
                "weight": 60,
                "muscle_groups": [{"name": "Chest", "impact": 100}],
            }
        ],
    }
    resp = client.post("/api/v1/workouts", json=plan, headers=_auth(token))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Agent Push Day"
    assert len(body["movements"]) == 1
    assert len(body["movements"][0]["sets"]) == 2

    persisted = Workout.query.filter_by(user_id=user.user_id).one()
    assert persisted.workout_name == "Agent Push Day"


def test_create_workout_rejects_empty_plan(client, app):
    user = _user("creator2")
    token, _ = ApiTokenService.generate(user.user_id)
    assert client.post("/api/v1/workouts", json={}, headers=_auth(token)).status_code == 400


def test_get_workout_404_for_other_user(client, app):
    alice = _user("a2")
    bob = _user("b2")
    bw = _workout(bob.user_id, "bw")
    a_token, _ = ApiTokenService.generate(alice.user_id)
    resp = client.get(f"/api/v1/workouts/{bw.workout_id}", headers=_auth(a_token))
    assert resp.status_code == 404

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


def test_me_includes_profile(client, app):
    user = _user("profiled")
    user.sex = "male"
    user.gym_experience = "intermediate"
    user.workout_goal = "strength"
    db.session.commit()
    token, _ = ApiTokenService.generate(user.user_id)
    body = client.get("/api/v1/me", headers=_auth(token)).get_json()
    assert body["profile"]["sex"] == "male"
    assert body["profile"]["gym_experience"] == "intermediate"
    assert body["profile"]["workout_goal"] == "strength"


def test_list_movements_and_muscle_groups(client, app):
    from app.models import Movement, MuscleGroup, MovementMuscleGroup
    user = _user("cataloger")
    token, _ = ApiTokenService.generate(user.user_id)
    mg = MuscleGroup(muscle_group_name="Chest")
    db.session.add(mg)
    db.session.flush()
    mv = Movement(movement_name="Bench Press")
    db.session.add(mv)
    db.session.flush()
    db.session.add(MovementMuscleGroup(
        movement_id=mv.movement_id, muscle_group_id=mg.muscle_group_id, target_percentage=100))
    db.session.commit()

    movements = client.get("/api/v1/movements", headers=_auth(token)).get_json()["movements"]
    assert any(
        m["name"] == "Bench Press" and m["muscle_groups"] == [{"name": "Chest", "impact": 100}]
        for m in movements
    )

    groups = client.get("/api/v1/muscle-groups", headers=_auth(token)).get_json()["muscle_groups"]
    assert any(grp["name"] == "Chest" for grp in groups)


def test_list_workouts_date_filter(client, app):
    user = _user("scheduler")
    token, _ = ApiTokenService.generate(user.user_id)
    db.session.add(Workout(user_id=user.user_id, workout_name="Wed",
                           workout_date=datetime(2026, 6, 17), is_completed=False))
    db.session.add(Workout(user_id=user.user_id, workout_name="Sat",
                           workout_date=datetime(2026, 6, 20), is_completed=False))
    db.session.commit()
    resp = client.get("/api/v1/workouts?from=2026-06-17&to=2026-06-17", headers=_auth(token))
    names = [w["name"] for w in resp.get_json()["workouts"]]
    assert names == ["Wed"]


def test_patch_reschedules_and_renames(client, app):
    user = _user("rescheduler")
    token, _ = ApiTokenService.generate(user.user_id)
    w = _workout(user.user_id, "Old Name")
    resp = client.patch(f"/api/v1/workouts/{w.workout_id}",
                        json={"date": "2026-07-01", "name": "New Name"}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "New Name"
    assert body["date"] == "2026-07-01"


def test_delete_workout_owner_only(client, app):
    user = _user("deleter")
    other = _user("deleter_other")
    token, _ = ApiTokenService.generate(user.user_id)
    other_token, _ = ApiTokenService.generate(other.user_id)
    w = _workout(user.user_id, "to delete")

    # another user's token cannot delete it
    assert client.delete(f"/api/v1/workouts/{w.workout_id}", headers=_auth(other_token)).status_code == 404
    # owner deletes -> 204, then it's gone
    assert client.delete(f"/api/v1/workouts/{w.workout_id}", headers=_auth(token)).status_code == 204
    assert client.get(f"/api/v1/workouts/{w.workout_id}", headers=_auth(token)).status_code == 404


def test_token_ui_renders_and_generates(client, app):
    """The 'Connect agent' settings page lists tokens and mints a new one (shown once)."""
    app.config["WTF_CSRF_ENABLED"] = False
    user = _user("ui_user")
    with client.session_transaction() as sess:
        sess["user_id"] = user.user_id

    assert client.get("/settings/api-tokens").status_code == 200

    resp = client.post("/settings/api-tokens", data={"name": "discord"})
    assert resp.status_code == 200
    assert b"naic_" in resp.data  # plaintext shown exactly once
    tokens = ApiTokenService.list_for_user(user.user_id)
    assert len(tokens) == 1 and tokens[0].name == "discord"

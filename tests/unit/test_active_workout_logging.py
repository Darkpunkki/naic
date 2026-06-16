"""Tests for server-authoritative active-workout set logging."""
from datetime import date

from app.models import (
    db,
    Movement,
    Rep,
    Set,
    SetEntry,
    User,
    Weight,
    Workout,
    WorkoutMovement,
)
from app.services.workout_service import WorkoutService


def _setup_workout(username="awlog_user", reps=10, weight=20, num_sets=1):
    """Create a user + workout with one movement and `num_sets` pending sets."""
    user = User(username=username, password_hash="x")
    db.session.add(user)
    db.session.flush()

    movement = Movement(movement_name="AW Log Movement")
    db.session.add(movement)
    db.session.flush()

    workout = Workout(
        user_id=user.user_id,
        workout_name="AW Log Workout",
        workout_date=date.today(),
        is_completed=False,
    )
    db.session.add(workout)
    db.session.flush()

    wm = WorkoutMovement(
        workout_id=workout.workout_id,
        movement_id=movement.movement_id,
        is_completed=False,
    )
    db.session.add(wm)
    db.session.flush()

    set_ids = []
    for i in range(num_sets):
        s = Set(workout_movement_id=wm.workout_movement_id, set_order=i + 1, status="pending")
        db.session.add(s)
        db.session.flush()
        db.session.add(Rep(set_id=s.set_id, rep_count=reps))
        db.session.add(Weight(set_id=s.set_id, weight_value=weight, is_bodyweight=False))
        set_ids.append(s.set_id)

    db.session.commit()
    return {
        "user_id": user.user_id,
        "workout_id": workout.workout_id,
        "wm_id": wm.workout_movement_id,
        "set_ids": set_ids,
    }


def test_log_active_set_persists_and_captures_planned_once(app):
    data = _setup_workout(reps=10, weight=20)
    set_id = data["set_ids"][0]

    result = WorkoutService.log_active_set(
        set_id=set_id, user_id=data["user_id"], reps=12, weight=25, status="completed"
    )

    assert result["status"] == "completed"
    saved = Set.query.get(set_id)
    assert saved.status == "completed"
    assert saved.reps[0].rep_count == 12
    assert float(saved.weights[0].weight_value) == 25.0

    entry = SetEntry.query.filter_by(set_id=set_id).first()
    assert entry is not None
    assert entry.reps == 12
    assert entry.planned_reps == 10  # prescribed value captured
    assert float(entry.planned_weight) == 20.0

    # A second log must NOT overwrite the originally captured planned values.
    WorkoutService.log_active_set(
        set_id=set_id, user_id=data["user_id"], reps=15, weight=30, status="completed"
    )
    entry = SetEntry.query.filter_by(set_id=set_id).first()
    assert entry.reps == 15
    assert entry.planned_reps == 10
    assert float(entry.planned_weight) == 20.0


def test_log_active_set_skipped_keeps_values(app):
    data = _setup_workout(reps=10, weight=20)
    set_id = data["set_ids"][0]

    WorkoutService.log_active_set(set_id=set_id, user_id=data["user_id"], status="skipped")

    saved = Set.query.get(set_id)
    assert saved.status == "skipped"
    assert saved.reps[0].rep_count == 10
    assert float(saved.weights[0].weight_value) == 20.0


def test_log_set_route_owner_200_nonowner_403(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    data = _setup_workout()
    workout_id, set_id = data["workout_id"], data["set_ids"][0]

    other = User(username="not_the_owner", password_hash="x")
    db.session.add(other)
    db.session.commit()
    other_id = other.user_id

    url = f"/active_workout/{workout_id}/sets/{set_id}/log"

    with client.session_transaction() as sess:
        sess["user_id"] = data["user_id"]
    resp = client.post(url, json={"reps": 11, "weight": 22, "status": "completed"})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert Set.query.get(set_id).status == "completed"

    with client.session_transaction() as sess:
        sess["user_id"] = other_id
    resp = client.post(url, json={"reps": 1, "weight": 1, "status": "completed"})
    assert resp.status_code == 403


def test_active_workout_get_hydrates_completed_status(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    data = _setup_workout(reps=10, weight=20)
    workout_id, set_id = data["workout_id"], data["set_ids"][0]

    WorkoutService.log_active_set(
        set_id=set_id, user_id=data["user_id"], reps=12, weight=25, status="completed"
    )

    with client.session_transaction() as sess:
        sess["user_id"] = data["user_id"]
    resp = client.get(f"/active_workout/{workout_id}")
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    assert '"status": "completed"' in body  # server status is shipped to the client
    assert '"reps": 12' in body  # saved actual value, not the prescribed 10


def test_complete_workout_finalizes_with_planned_intact(app):
    data = _setup_workout(reps=10, weight=20, num_sets=2)
    completed_set, skipped_set = data["set_ids"]

    WorkoutService.log_active_set(
        set_id=completed_set, user_id=data["user_id"], reps=12, weight=25, status="completed"
    )
    WorkoutService.log_active_set(
        set_id=skipped_set, user_id=data["user_id"], status="skipped"
    )

    workout = WorkoutService.complete_workout(data["workout_id"], {}, date.today())

    assert workout.is_completed is True
    wm = WorkoutMovement.query.get(data["wm_id"])
    assert wm.is_completed is True

    assert Set.query.get(completed_set).status == "completed"
    assert Set.query.get(skipped_set).status == "skipped"

    # Completion must not clobber the planned value captured during incremental logging.
    entry = SetEntry.query.filter_by(set_id=completed_set).first()
    assert entry.planned_reps == 10
    assert entry.reps == 12


def test_skipped_sets_excluded_from_impact(app):
    from app.models import MuscleGroup, MovementMuscleGroup
    from app.services.stats_service import StatsService

    data = _setup_workout(reps=10, weight=20, num_sets=2)
    wm = WorkoutMovement.query.get(data["wm_id"])

    mg = MuscleGroup(muscle_group_name="TestChest")
    db.session.add(mg)
    db.session.flush()
    db.session.add(MovementMuscleGroup(
        movement_id=wm.movement_id,
        muscle_group_id=mg.muscle_group_id,
        target_percentage=100,
    ))
    db.session.commit()

    completed_set, skipped_set = data["set_ids"]
    WorkoutService.log_active_set(
        set_id=completed_set, user_id=data["user_id"], reps=10, weight=20, status="completed"
    )
    WorkoutService.log_active_set(set_id=skipped_set, user_id=data["user_id"], status="skipped")

    totals = StatsService.build_workout_impacts(Workout.query.get(data["workout_id"]))
    assert len(totals) == 1
    mg_totals = next(iter(totals.values()))
    assert round(mg_totals["sets"]) == 1   # only the completed set is counted
    assert mg_totals["reps"] == 10         # the skipped set's reps are excluded


def test_view_workout_marks_skipped(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    data = _setup_workout(reps=10, weight=20, num_sets=2)
    completed_set, skipped_set = data["set_ids"]

    WorkoutService.log_active_set(
        set_id=completed_set, user_id=data["user_id"], reps=10, weight=20, status="completed"
    )
    WorkoutService.log_active_set(set_id=skipped_set, user_id=data["user_id"], status="skipped")
    WorkoutService.complete_workout(data["workout_id"], {}, date.today())

    with client.session_transaction() as sess:
        sess["user_id"] = data["user_id"]
    resp = client.get(f"/workout/{data['workout_id']}")
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    assert "1 skipped" in body     # skipped set surfaced distinctly
    assert "status-tag" in body    # per-movement status label rendered

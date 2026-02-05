from datetime import date, datetime, timedelta

import pytest

from app.models import Movement, User, Workout, WorkoutMovement, db
from app.services.movement_service import MovementService
from app.services.workout_service import WorkoutService


def _create_user(username: str) -> int:
    user = User(username=username, password_hash="x")
    db.session.add(user)
    db.session.commit()
    return user.user_id


def _create_workout_with_sets(user_id: int, name: str, workout_date: datetime, completed: bool = False) -> int:
    movement = Movement(movement_name=f"{name} Movement")
    db.session.add(movement)
    db.session.flush()

    workout = Workout(
        user_id=user_id,
        workout_name=name,
        workout_date=workout_date,
        is_completed=completed
    )
    db.session.add(workout)
    db.session.flush()

    workout_movement = WorkoutMovement(
        workout_id=workout.workout_id,
        movement_id=movement.movement_id,
        is_completed=completed
    )
    db.session.add(workout_movement)
    db.session.commit()

    MovementService._create_sets_for_workout_movement(
        workout_movement_id=workout_movement.workout_movement_id,
        set_count=3,
        reps_per_set=10,
        weight_value=20.0,
        is_bodyweight=False
    )
    return workout.workout_id


def test_start_workout_now_always_duplicates_source(app):
    with app.app_context():
        user_id = _create_user("launcher_duplicate_user")
        source_date = datetime.utcnow() - timedelta(days=2)
        source_workout_id = _create_workout_with_sets(
            user_id=user_id,
            name="Leg Day",
            workout_date=source_date,
            completed=False
        )

        duplicated = WorkoutService.start_workout_now(user_id, source_workout_id, target_date=date.today())
        source = Workout.query.get(source_workout_id)

        assert duplicated.workout_id != source_workout_id
        assert duplicated.user_id == user_id
        assert duplicated.workout_name.endswith("(Copy)")
        assert duplicated.workout_date.date() == date.today()
        assert source.workout_date.date() == source_date.date()
        assert len(duplicated.workout_movements) == len(source.workout_movements)
        assert len(duplicated.workout_movements[0].sets) == len(source.workout_movements[0].sets)


def test_start_workout_now_rejects_non_owner(app):
    with app.app_context():
        owner_id = _create_user("launcher_owner")
        other_id = _create_user("launcher_other")
        workout_id = _create_workout_with_sets(
            user_id=owner_id,
            name="Push Day",
            workout_date=datetime.utcnow()
        )

        with pytest.raises(ValueError) as exc_info:
            WorkoutService.start_workout_now(other_id, workout_id, target_date=date.today())
        assert "Unauthorized" in str(exc_info.value)


def test_start_workout_now_duplicates_even_when_source_is_today(app):
    with app.app_context():
        user_id = _create_user("launcher_today_copy_user")
        source_workout_id = _create_workout_with_sets(
            user_id=user_id,
            name="Today Source",
            workout_date=datetime.utcnow(),
            completed=False
        )

        copied = WorkoutService.start_workout_now(user_id, source_workout_id, target_date=date.today())

        assert copied.workout_id != source_workout_id
        assert copied.workout_date.date() == date.today()


def test_quick_start_route_creates_today_workout(client, app):
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        user_id = _create_user("quick_start_user")

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.post("/workouts/quick_start", json={})
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    workout_id = payload["workout_id"]

    with app.app_context():
        workout = Workout.query.get(workout_id)
        assert workout is not None
        assert workout.user_id == user_id
        assert workout.workout_name == f"Quick Workout - {date.today().strftime('%A')}"
        assert workout.workout_date.date() == date.today()
        assert workout.is_completed is False


def test_start_now_route_duplicates_workout(client, app):
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        user_id = _create_user("start_now_user")
        source_workout_id = _create_workout_with_sets(
            user_id=user_id,
            name="Upper Body",
            workout_date=datetime.utcnow() - timedelta(days=1),
            completed=True
        )

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.post(f"/workout/{source_workout_id}/start_now", json={})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["duplicated"] is True
    assert payload["workout_id"] != source_workout_id

    with app.app_context():
        new_workout = Workout.query.get(payload["workout_id"])
        source_workout = Workout.query.get(source_workout_id)
        assert new_workout is not None
        assert source_workout is not None
        assert new_workout.workout_date.date() == date.today()
        assert len(new_workout.workout_movements) == len(source_workout.workout_movements)
        assert source_workout.workout_date.date() != date.today()


def test_start_workout_page_includes_launcher_sections(client, app):
    with app.app_context():
        user_id = _create_user("launcher_page_user")
        _create_workout_with_sets(
            user_id=user_id,
            name="Completed Template",
            workout_date=datetime.utcnow() - timedelta(days=3),
            completed=True
        )
        _create_workout_with_sets(
            user_id=user_id,
            name="Today Plan",
            workout_date=datetime.utcnow(),
            completed=False
        )

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/start_workout")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Continue Today" in body
    assert "Start From Existing Workout" in body
    assert "Quick Workout" in body
    assert "Generate New Workout" in body
    assert "Completed Template" in body


def test_cleanup_empty_quick_workouts_deletes_only_empty_quick(app):
    with app.app_context():
        user_id = _create_user("cleanup_quick_user")
        quick_empty = WorkoutService.create_blank_workout(
            user_id=user_id,
            workout_date=date.today(),
            name="Quick Workout - Monday"
        )
        quick_with_movement_id = _create_workout_with_sets(
            user_id=user_id,
            name="Quick Workout - Tuesday",
            workout_date=datetime.utcnow(),
            completed=False
        )
        regular_empty = WorkoutService.create_blank_workout(
            user_id=user_id,
            workout_date=date.today(),
            name="New workout"
        )

        deleted_count = WorkoutService.cleanup_empty_quick_start_workouts(user_id)

        assert deleted_count == 1
        assert Workout.query.get(quick_empty.workout_id) is None
        assert Workout.query.get(quick_with_movement_id) is not None
        assert Workout.query.get(regular_empty.workout_id) is not None


def test_start_workout_route_cleans_empty_quick_workouts(client, app):
    with app.app_context():
        user_id = _create_user("cleanup_route_user")
        stale_quick = WorkoutService.create_blank_workout(
            user_id=user_id,
            workout_date=date.today(),
            name="Quick Workout - Friday"
        )
        stale_quick_id = stale_quick.workout_id
        _create_workout_with_sets(
            user_id=user_id,
            name="Template",
            workout_date=datetime.utcnow(),
            completed=False
        )

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/start_workout")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Quick Workout - Friday" not in body

    with app.app_context():
        assert Workout.query.get(stale_quick_id) is None


def test_active_workout_sets_auto_cleanup_flag_for_empty_quick(client, app):
    with app.app_context():
        user_id = _create_user("active_cleanup_flag_user")
        quick_empty = WorkoutService.create_blank_workout(
            user_id=user_id,
            workout_date=date.today(),
            name="Quick Workout - Sunday"
        )
        quick_empty_id = quick_empty.workout_id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get(f"/active_workout/{quick_empty_id}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "const autoCleanupEmptyWorkout = true;" in body


def test_existing_workout_list_is_collapsed_by_default_when_long(client, app):
    with app.app_context():
        user_id = _create_user("launcher_long_list_user")
        for index in range(12):
            _create_workout_with_sets(
                user_id=user_id,
                name=f"Template {index}",
                workout_date=datetime.utcnow() - timedelta(days=index),
                completed=(index % 2 == 0)
            )

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/start_workout")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="existingWorkoutList"' in body
    assert 'data-initial-visible="10"' in body
    assert 'id="toggleExistingWorkouts"' in body
    assert "Show More" in body


def test_launcher_post_routes_require_auth(client, app):
    app.config["WTF_CSRF_ENABLED"] = False

    start_now_response = client.post("/workout/999/start_now", json={})
    quick_start_response = client.post("/workouts/quick_start", json={})

    assert start_now_response.status_code == 401
    assert quick_start_response.status_code == 401

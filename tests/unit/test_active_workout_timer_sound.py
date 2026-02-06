import re
from datetime import datetime
from pathlib import Path

from app.models import Movement, Rep, Set, User, Weight, Workout, WorkoutMovement, db


def _create_active_workout(user_id):
    movement = Movement(movement_name="Timer Sound Test Movement")
    db.session.add(movement)
    db.session.flush()

    workout = Workout(
        user_id=user_id,
        workout_name="Timer Sound Workout",
        workout_date=datetime.utcnow(),
        is_completed=False,
    )
    db.session.add(workout)
    db.session.flush()

    workout_movement = WorkoutMovement(
        workout_id=workout.workout_id,
        movement_id=movement.movement_id,
        is_completed=False,
    )
    db.session.add(workout_movement)
    db.session.flush()

    set_row = Set(
        workout_movement_id=workout_movement.workout_movement_id,
        set_order=1,
        status="pending",
    )
    db.session.add(set_row)
    db.session.flush()

    db.session.add(Rep(set_id=set_row.set_id, rep_count=10))
    db.session.add(Weight(set_id=set_row.set_id, weight_value=20, is_bodyweight=False))
    db.session.commit()
    return workout


def test_active_workout_has_timer_sound_toggle_default_off(client, app):
    with app.app_context():
        user = User(username="timer_sound_user", password_hash="x")
        db.session.add(user)
        db.session.commit()

        workout = _create_active_workout(user.user_id)
        user_id = user.user_id
        workout_id = workout.workout_id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get(f"/active_workout/{workout_id}")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    match = re.search(r'<input[^>]*id="timerSoundToggle"[^>]*>', body)
    assert match is not None
    assert "checked" not in match.group(0)


def test_timer_sound_state_declared_before_toggle_setup_call():
    script_path = Path(__file__).resolve().parents[2] / "static" / "js" / "active_template_scripts.js"
    with script_path.open("r", encoding="utf-8") as script_file:
        script = script_file.read()

    declaration_index = script.find("let isTimerSoundEnabled = false;")
    setup_call_index = script.find("setupTimerSoundToggle();")

    assert declaration_index != -1
    assert setup_call_index != -1
    assert declaration_index < setup_call_index


def test_active_workout_has_set_history_edit_controls(client, app):
    with app.app_context():
        user = User(username="edit_sets_user", password_hash="x")
        db.session.add(user)
        db.session.commit()

        workout = _create_active_workout(user.user_id)
        user_id = user.user_id
        workout_id = workout.workout_id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get(f"/active_workout/{workout_id}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert 'id="setHistoryList"' in body
    assert 'id="saveEditSetBtn"' in body
    assert 'id="cancelEditSetBtn"' in body

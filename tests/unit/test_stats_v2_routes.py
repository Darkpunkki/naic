from datetime import datetime

from app.models import (
    db,
    User,
    MuscleGroup,
    Movement,
    MovementMuscleGroup,
    Workout,
    WorkoutMovement,
    Set,
    Rep,
    Weight,
    SetEntry,
)
from app.services.stats_service import StatsService
from app.services.stats_v2_service import StatsV2Service


def seed_v2_data():
    user = User(username="v2_route_user", password_hash="x", bodyweight=75)
    db.session.add(user)
    db.session.commit()

    back = MuscleGroup(muscle_group_name="Back")
    db.session.add(back)
    db.session.commit()

    movement = Movement(movement_name="Deadlift")
    db.session.add(movement)
    db.session.commit()

    db.session.add(
        MovementMuscleGroup(
            movement_id=movement.movement_id,
            muscle_group_id=back.muscle_group_id,
            target_percentage=100,
        )
    )
    db.session.commit()

    workout = Workout(
        user_id=user.user_id,
        workout_name="Route Test",
        workout_date=datetime.utcnow(),
        is_completed=True,
    )
    db.session.add(workout)
    db.session.commit()

    wm = WorkoutMovement(workout_id=workout.workout_id, movement_id=movement.movement_id)
    db.session.add(wm)
    db.session.commit()

    set_row = Set(workout_movement_id=wm.workout_movement_id, set_order=1, status="completed")
    db.session.add(set_row)
    db.session.commit()

    db.session.add_all([
        Rep(set_id=set_row.set_id, rep_count=5),
        Weight(set_id=set_row.set_id, weight_value=100, is_bodyweight=False),
        SetEntry(set_id=set_row.set_id, entry_order=1, reps=5, weight_value=100, is_bodyweight=False),
    ])
    db.session.commit()

    StatsService.rebuild_workout_impacts(workout, commit=True)
    StatsV2Service.rebuild_workout_summaries(workout)

    return user.user_id, movement.movement_id, movement.movement_name


def test_stats_v2_endpoints(client, app):
    with app.app_context():
        user_id, movement_id, movement_name = seed_v2_data()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/stats/overview?period=week")
    assert response.status_code == 200
    payload = response.get_json()
    assert "total_volume" in payload

    response = client.get("/stats/movements?period=week")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["movements"][0]["movement_name"] == movement_name

    response = client.get(f"/stats/movements/{movement_id}/series?period=week")
    assert response.status_code == 200
    payload = response.get_json()
    assert "series" in payload

    response = client.get("/stats/muscles?period=week")
    assert response.status_code == 200
    payload = response.get_json()
    assert "distribution" in payload

    response = client.get("/stats/records")
    assert response.status_code == 200
    payload = response.get_json()
    assert "records" in payload

    response = client.get("/stats/adherence?period=week")
    assert response.status_code == 200
    payload = response.get_json()
    assert "avg_completion_rate" in payload

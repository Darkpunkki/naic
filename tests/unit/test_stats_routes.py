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


def seed_completed_workout():
    user = User(username="stat_user", password_hash="x", bodyweight=80)
    db.session.add(user)
    db.session.commit()

    chest = MuscleGroup(muscle_group_name="Chest")
    db.session.add(chest)
    db.session.commit()

    movement = Movement(movement_name="Push Up")
    db.session.add(movement)
    db.session.commit()

    db.session.add(
        MovementMuscleGroup(
            movement_id=movement.movement_id,
            muscle_group_id=chest.muscle_group_id,
            target_percentage=100,
        )
    )
    db.session.commit()

    workout = Workout(user_id=user.user_id, workout_name="Stat Test", workout_date=datetime.utcnow(), is_completed=True)
    db.session.add(workout)
    db.session.commit()

    wm = WorkoutMovement(workout_id=workout.workout_id, movement_id=movement.movement_id)
    db.session.add(wm)
    db.session.commit()

    s = Set(workout_movement_id=wm.workout_movement_id, set_order=1)
    db.session.add(s)
    db.session.commit()

    db.session.add_all([
        Rep(set_id=s.set_id, rep_count=12),
        Weight(set_id=s.set_id, weight_value=0, is_bodyweight=True),
        SetEntry(set_id=s.set_id, entry_order=1, reps=12, weight_value=0, is_bodyweight=True),
    ])
    db.session.commit()

    StatsService.rebuild_workout_impacts(workout, commit=True)
    return user


def test_stats_data_endpoint(client, app):
    with app.app_context():
        user = seed_completed_workout()

    with client.session_transaction() as sess:
        sess['user_id'] = user.user_id

    response = client.get('/stats/data?period=week')
    assert response.status_code == 200
    payload = response.get_json()
    assert 'totals_by_muscle' in payload
    assert payload['totals_by_muscle']['Chest'] > 0

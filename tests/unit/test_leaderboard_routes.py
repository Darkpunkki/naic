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


def create_user_with_workout(username, reps, weight):
    user = User(username=username, password_hash="x", bodyweight=80)
    db.session.add(user)
    db.session.commit()

    movement = Movement.query.filter_by(movement_name="Bench").first()
    if not movement:
        movement = Movement(movement_name="Bench")
        db.session.add(movement)
        db.session.commit()

    chest = MuscleGroup.query.filter_by(muscle_group_name="Chest").first()
    if not chest:
        chest = MuscleGroup(muscle_group_name="Chest")
        db.session.add(chest)
        db.session.commit()
        db.session.add(MovementMuscleGroup(
            movement_id=movement.movement_id,
            muscle_group_id=chest.muscle_group_id,
            target_percentage=100,
        ))
        db.session.commit()

    workout = Workout(user_id=user.user_id, workout_name="LB", workout_date=datetime.utcnow(), is_completed=True)
    db.session.add(workout)
    db.session.commit()

    wm = WorkoutMovement(workout_id=workout.workout_id, movement_id=movement.movement_id)
    db.session.add(wm)
    db.session.commit()

    s = Set(workout_movement_id=wm.workout_movement_id, set_order=1)
    db.session.add(s)
    db.session.commit()

    db.session.add_all([
        Rep(set_id=s.set_id, rep_count=reps),
        Weight(set_id=s.set_id, weight_value=weight, is_bodyweight=False),
        SetEntry(set_id=s.set_id, entry_order=1, reps=reps, weight_value=weight, is_bodyweight=False),
    ])
    db.session.commit()

    StatsService.rebuild_workout_impacts(workout, commit=True)
    return user


def test_leaderboard_data_endpoint(client, app):
    with app.app_context():
        user1 = create_user_with_workout("alpha", 10, 50)
        create_user_with_workout("bravo", 8, 40)

    with client.session_transaction() as sess:
        sess['user_id'] = user1.user_id

    response = client.get('/leaderboard/data?period=week')
    assert response.status_code == 200
    payload = response.get_json()
    assert 'users' in payload
    assert any(u['username'] == 'alpha' for u in payload['users'])

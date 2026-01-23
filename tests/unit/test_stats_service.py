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


def test_effective_load_bodyweight_minor(app):
    app.config["IMPACT_BASE_LOAD"] = 10
    app.config["IMPACT_EXTERNAL_WEIGHT_FACTOR"] = 1.0
    app.config["IMPACT_BODYWEIGHT_FACTOR"] = 0.25

    with app.app_context():
        load = StatsService.effective_load(0, True, 100)
        assert load == 35.0


def test_effective_load_zero_weight_non_bodyweight(app):
    app.config["IMPACT_BASE_LOAD"] = 10
    app.config["IMPACT_EXTERNAL_WEIGHT_FACTOR"] = 1.0
    app.config["IMPACT_BODYWEIGHT_FACTOR"] = 0.25

    with app.app_context():
        load = StatsService.effective_load(0, False, 100)
        assert load == 10.0


def test_calculate_muscle_group_impact_normalizes(app):
    app.config["IMPACT_BASE_LOAD"] = 10
    app.config["IMPACT_EXTERNAL_WEIGHT_FACTOR"] = 1.0
    app.config["IMPACT_BODYWEIGHT_FACTOR"] = 0.25

    with app.app_context():
        user = User(username="tester", password_hash="x", bodyweight=100)
        db.session.add(user)
        db.session.commit()

        chest = MuscleGroup(muscle_group_name="Chest")
        triceps = MuscleGroup(muscle_group_name="Triceps")
        db.session.add_all([chest, triceps])
        db.session.commit()

        movement = Movement(movement_name="Bench Press")
        db.session.add(movement)
        db.session.commit()

        db.session.add_all([
            MovementMuscleGroup(movement_id=movement.movement_id, muscle_group_id=chest.muscle_group_id, target_percentage=70),
            MovementMuscleGroup(movement_id=movement.movement_id, muscle_group_id=triceps.muscle_group_id, target_percentage=70),
        ])
        db.session.commit()

        workout = Workout(user_id=user.user_id, workout_name="Test", workout_date=datetime.utcnow(), is_completed=True)
        db.session.add(workout)
        db.session.commit()

        wm = WorkoutMovement(workout_id=workout.workout_id, movement_id=movement.movement_id)
        db.session.add(wm)
        db.session.commit()

        s = Set(workout_movement_id=wm.workout_movement_id, set_order=1)
        db.session.add(s)
        db.session.commit()

        db.session.add_all([
            Rep(set_id=s.set_id, rep_count=10),
            Weight(set_id=s.set_id, weight_value=50, is_bodyweight=False),
            SetEntry(set_id=s.set_id, entry_order=1, reps=10, weight_value=50, is_bodyweight=False),
        ])
        db.session.commit()

        impacts = wm.calculate_muscle_group_impact()
        assert round(impacts["Chest"], 2) == 300.0
        assert round(impacts["Triceps"], 2) == 300.0

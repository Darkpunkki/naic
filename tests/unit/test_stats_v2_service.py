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
    WorkoutSessionSummary,
    WorkoutMovementStats,
    MovementDailySummary,
    MuscleGroupDailySummary,
    PersonalRecord,
)
from app.services.stats_service import StatsService
from app.services.stats_v2_service import StatsV2Service


def seed_completed_workout():
    user = User(username="v2_user", password_hash="x", bodyweight=80)
    db.session.add(user)
    db.session.commit()

    chest = MuscleGroup(muscle_group_name="Chest")
    db.session.add(chest)
    db.session.commit()

    movement = Movement(movement_name="Bench Press")
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

    workout = Workout(
        user_id=user.user_id,
        workout_name="V2 Test",
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
        Rep(set_id=set_row.set_id, rep_count=10),
        Weight(set_id=set_row.set_id, weight_value=50, is_bodyweight=False),
        SetEntry(
            set_id=set_row.set_id,
            entry_order=1,
            reps=10,
            weight_value=50,
            is_bodyweight=False,
            rpe=8.5,
            rest_seconds=90,
        ),
    ])
    db.session.commit()

    StatsService.rebuild_workout_impacts(workout, commit=True)
    StatsV2Service.rebuild_workout_summaries(workout)

    return user, workout, movement


def test_stats_v2_summaries_created(app):
    with app.app_context():
        user, workout, movement = seed_completed_workout()

        summary = WorkoutSessionSummary.query.filter_by(workout_id=workout.workout_id).first()
        assert summary is not None
        assert float(summary.total_volume) > 0
        assert float(summary.avg_rpe) == 8.5

        movement_stats = WorkoutMovementStats.query.filter_by(workout_id=workout.workout_id).first()
        assert movement_stats is not None
        assert float(movement_stats.e1rm) > 0
        assert float(movement_stats.avg_rest_seconds) == 90

        daily = MovementDailySummary.query.filter_by(
            user_id=user.user_id,
            movement_id=movement.movement_id,
            summary_date=workout.workout_date.date(),
        ).first()
        assert daily is not None

        muscle_daily = MuscleGroupDailySummary.query.filter_by(
            user_id=user.user_id,
            summary_date=workout.workout_date.date(),
        ).first()
        assert muscle_daily is not None

        pr = PersonalRecord.query.filter_by(
            user_id=user.user_id,
            movement_id=movement.movement_id,
            record_type="e1rm",
        ).first()
        assert pr is not None

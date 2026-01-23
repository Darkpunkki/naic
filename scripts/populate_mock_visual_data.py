import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure repo root is on sys.path so `app` can be imported when run directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from app.models import (
    db,
    User,
    Workout,
    Movement,
    WorkoutMovement,
    Set,
    Rep,
    Weight,
    SetEntry,
)
from app.services.stats_service import StatsService

USERNAMES = ["jimi", "janna", "niko", "testiseppo", "aman"]
WORKOUTS_PER_USER = 10

# Simple tunables for mock data
MOVEMENTS_PER_WORKOUT = (3, 6)
SETS_PER_MOVEMENT = (2, 5)
REPS_RANGE = (6, 15)
WEIGHT_RANGE = (10, 90)
BODYWEIGHT_CHANCE = 0.2


def get_or_create_users():
    users = {u.username: u for u in User.query.filter(User.username.in_(USERNAMES)).all()}
    created = 0
    for username in USERNAMES:
        if username in users:
            continue
        user = User(username=username, password_hash="mock_password_hash")
        db.session.add(user)
        users[username] = user
        created += 1
    if created:
        db.session.commit()
    return [users[name] for name in USERNAMES]


def random_workout_date():
    days_ago = random.randint(0, 9)
    base = datetime.now() - timedelta(days=days_ago)
    hour = random.randint(6, 21)
    minute = random.randint(0, 59)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def create_mock_workouts():
    movements = Movement.query.all()
    if not movements:
        print("No movements found. Seed movements before running this script.")
        return

    users = get_or_create_users()
    created = 0

    for user in users:
        for idx in range(WORKOUTS_PER_USER):
            workout = Workout(
                user_id=user.user_id,
                workout_name=f"Mock Workout {idx + 1}",
                workout_date=random_workout_date(),
                is_completed=True,
            )
            db.session.add(workout)
            db.session.flush()

            movement_count = random.randint(*MOVEMENTS_PER_WORKOUT)
            for _ in range(movement_count):
                movement = random.choice(movements)
                wm = WorkoutMovement(workout_id=workout.workout_id, movement_id=movement.movement_id)
                db.session.add(wm)
                db.session.flush()

                set_count = random.randint(*SETS_PER_MOVEMENT)
                for set_index in range(set_count):
                    workout_set = Set(workout_movement_id=wm.workout_movement_id, set_order=set_index + 1)
                    db.session.add(workout_set)
                    db.session.flush()

                    reps = random.randint(*REPS_RANGE)
                    is_bodyweight = random.random() < BODYWEIGHT_CHANCE
                    weight_value = 0 if is_bodyweight else random.randint(*WEIGHT_RANGE)

                    rep_record = Rep(set_id=workout_set.set_id, rep_count=reps)
                    weight_record = Weight(
                        set_id=workout_set.set_id,
                        weight_value=weight_value,
                        is_bodyweight=is_bodyweight,
                    )
                    entry_record = SetEntry(
                        set_id=workout_set.set_id,
                        entry_order=1,
                        reps=reps,
                        weight_value=weight_value,
                        is_bodyweight=is_bodyweight,
                    )
                    db.session.add_all([rep_record, weight_record, entry_record])

            StatsService.rebuild_workout_impacts(workout, commit=False)
            created += 1

    db.session.commit()
    print(f"Created {created} workouts across {len(users)} users.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        create_mock_workouts()

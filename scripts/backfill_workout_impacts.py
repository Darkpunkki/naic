import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from app.models import Workout
from app.services.stats_service import StatsService


def backfill_workout_impacts():
    workouts = Workout.query.filter_by(is_completed=True).all()
    for workout in workouts:
        StatsService.rebuild_workout_impacts(workout, commit=False)
    from app.models import db
    db.session.commit()
    print(f"Backfill complete. Rebuilt impacts for {len(workouts)} workouts.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        backfill_workout_impacts()

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from app.models import Workout
from app.services.stats_v2_service import StatsV2Service


def backfill_stats_v2():
    workouts = Workout.query.filter_by(is_completed=True).order_by(Workout.workout_date.asc()).all()
    processed = 0
    for workout in workouts:
        StatsV2Service.rebuild_workout_summaries(workout)
        processed += 1
    print(f"Backfill complete. Processed {processed} workouts.")


if __name__ == "__main__":
    app = create_app({"SKIP_NLTK_DOWNLOAD": True})
    with app.app_context():
        backfill_stats_v2()

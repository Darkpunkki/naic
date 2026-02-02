# seed_workouts.py
from datetime import datetime
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from app.models import Workout, db

def seed_workouts():
    """
    Add sample workouts to the database.
    """
    app = create_app()
    with app.app_context():
        # Create some workouts
        w1 = Workout(workout_name="Chest Day", workout_date=datetime(2024, 12, 28), user_id=1)
        w2 = Workout(workout_name="Leg Day", workout_date=datetime(2024, 12, 29), user_id=1)
        w3 = Workout(workout_name="Back Day", workout_date=datetime(2024, 12, 30), user_id=1)

        db.session.add_all([w1, w2, w3])
        db.session.commit()

        print("Workouts seeded successfully!")

if __name__ == "__main__":
    seed_workouts()

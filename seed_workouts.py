# seed_workouts.py
from datetime import datetime
from app import app, db
from models import Workout

def seed_workouts():
    """
    Add sample workouts to the database.
    """
    with app.app_context():
        # Create some workouts
        w1 = Workout(name="Chest Day", date=datetime(2024, 12, 28).date(), status="planned")
        w2 = Workout(name="Leg Day", date=datetime(2024, 12, 29).date(), status="planned")
        w3 = Workout(name="Back Day", date=datetime(2024, 12, 30).date(), status="planned")

        db.session.add_all([w1, w2, w3])
        db.session.commit()

        print("Workouts seeded successfully!")

if __name__ == "__main__":
    seed_workouts()

from app import app, db
from models import Movement

def seed_movements():
    """
    Add sample movements (exercises) to the database.
    """
    with app.app_context():
        bench_press = Movement(name="Bench Press", description="Chest exercise with a barbell")
        squat = Movement(name="Squat", description="Leg exercise with a barbell")
        deadlift = Movement(name="Deadlift", description="Compound back/leg exercise")
        overhead_press = Movement(name="Overhead Press", description="Shoulder press with a barbell")

        db.session.add_all([bench_press, squat, deadlift, overhead_press])
        db.session.commit()

        print("Movements seeded successfully!")

if __name__ == "__main__":
    seed_movements()

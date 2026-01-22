from app import create_app
from app.models import Movement, db

def seed_movements():
    """
    Add sample movements (exercises) to the database.
    """
    app = create_app()
    with app.app_context():
        bench_press = Movement(movement_name="Bench Press", movement_description="Chest exercise with a barbell")
        squat = Movement(movement_name="Squat", movement_description="Leg exercise with a barbell")
        deadlift = Movement(movement_name="Deadlift", movement_description="Compound back/leg exercise")
        overhead_press = Movement(movement_name="Overhead Press", movement_description="Shoulder press with a barbell")

        db.session.add_all([bench_press, squat, deadlift, overhead_press])
        db.session.commit()

        print("Movements seeded successfully!")

if __name__ == "__main__":
    seed_movements()

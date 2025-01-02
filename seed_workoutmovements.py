# seed_workoutmovements.py
from app import app, db
from models import Workout, Movement, WorkoutMovement

def seed_workoutmovements():
    """
    Link workouts to movements (full workout plans).
    """
    with app.app_context():
        # Example: Grab existing workouts by name
        chest_day = Workout.query.filter_by(name="Chest Day").first()
        leg_day = Workout.query.filter_by(name="Leg Day").first()
        back_day = Workout.query.filter_by(name="Back Day").first()

        # Example: Grab movements by name
        bench_press = Movement.query.filter_by(name="Bench Press").first()
        squat = Movement.query.filter_by(name="Squat").first()
        deadlift = Movement.query.filter_by(name="Deadlift").first()
        overhead_press = Movement.query.filter_by(name="Overhead Press").first()

        # If any are missing, bail out or create them:
        if not (chest_day and leg_day and back_day and bench_press and squat and deadlift and overhead_press):
            print("Error: Some workouts/movements are missing. Seed those first or check names!")
            return

        # Example 1: Chest Day plan
        wm1 = WorkoutMovement(workout_id=chest_day.id, movement_id=bench_press.id, sets=4, reps_per_set=10, weight=60.0)
        wm2 = WorkoutMovement(workout_id=chest_day.id, movement_id=overhead_press.id, sets=3, reps_per_set=8, weight=40.0)

        # Example 2: Leg Day plan
        wm3 = WorkoutMovement(workout_id=leg_day.id, movement_id=squat.id, sets=4, reps_per_set=8, weight=80.0)
        wm4 = WorkoutMovement(workout_id=leg_day.id, movement_id=deadlift.id, sets=3, reps_per_set=5, weight=100.0)

        # Example 3: Back Day plan
        wm5 = WorkoutMovement(workout_id=back_day.id, movement_id=deadlift.id, sets=5, reps_per_set=5, weight=120.0)
        wm6 = WorkoutMovement(workout_id=back_day.id, movement_id=bench_press.id, sets=3, reps_per_set=12, weight=50.0)

        db.session.add_all([wm1, wm2, wm3, wm4, wm5, wm6])
        db.session.commit()

        print("WorkoutMovements seeded successfully!")

if __name__ == "__main__":
    seed_workoutmovements()

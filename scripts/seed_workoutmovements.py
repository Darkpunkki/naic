# seed_workoutmovements.py
from app import create_app
from app.models import Movement, Workout, WorkoutMovement, db

def seed_workoutmovements():
    """
    Link workouts to movements (full workout plans).
    """
    app = create_app()
    with app.app_context():
        # Example: Grab existing workouts by name
        chest_day = Workout.query.filter_by(workout_name="Chest Day").first()
        leg_day = Workout.query.filter_by(workout_name="Leg Day").first()
        back_day = Workout.query.filter_by(workout_name="Back Day").first()

        # Example: Grab movements by name
        bench_press = Movement.query.filter_by(movement_name="Bench Press").first()
        squat = Movement.query.filter_by(movement_name="Squat").first()
        deadlift = Movement.query.filter_by(movement_name="Deadlift").first()
        overhead_press = Movement.query.filter_by(movement_name="Overhead Press").first()

        # If any are missing, bail out or create them:
        if not (chest_day and leg_day and back_day and bench_press and squat and deadlift and overhead_press):
            print("Error: Some workouts/movements are missing. Seed those first or check names!")
            return

        # Example 1: Chest Day plan
        wm1 = WorkoutMovement(workout_id=chest_day.workout_id, movement_id=bench_press.movement_id)
        wm2 = WorkoutMovement(workout_id=chest_day.workout_id, movement_id=overhead_press.movement_id)

        # Example 2: Leg Day plan
        wm3 = WorkoutMovement(workout_id=leg_day.workout_id, movement_id=squat.movement_id)
        wm4 = WorkoutMovement(workout_id=leg_day.workout_id, movement_id=deadlift.movement_id)

        # Example 3: Back Day plan
        wm5 = WorkoutMovement(workout_id=back_day.workout_id, movement_id=deadlift.movement_id)
        wm6 = WorkoutMovement(workout_id=back_day.workout_id, movement_id=bench_press.movement_id)

        db.session.add_all([wm1, wm2, wm3, wm4, wm5, wm6])
        db.session.commit()

        print("WorkoutMovements seeded successfully!")

if __name__ == "__main__":
    seed_workoutmovements()

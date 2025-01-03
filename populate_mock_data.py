from datetime import datetime, timedelta
import random
from app import db, User, Workout, Movement, MuscleGroup, MovementMuscleGroup, WorkoutMovement

# Predefined mock data
MOVEMENTS = [
    {"name": "Bench Press", "muscle_groups": {"Chest": 70, "Shoulders": 20, "Triceps": 10}},
    {"name": "Deadlift", "muscle_groups": {"Back": 50, "Legs": 30, "Forearms": 20}},
    {"name": "Squats", "muscle_groups": {"Legs": 80, "Core": 20}},
    {"name": "Pull-Ups", "muscle_groups": {"Back": 60, "Biceps": 30, "Shoulders": 10}},
    {"name": "Overhead Press", "muscle_groups": {"Shoulders": 70, "Triceps": 30}},
]

def get_or_create_user(username="jimi"):
    """Retrieve or create a user with the username 'jimi'."""
    user = User.query.filter_by(username=username).first()
    if not user:
        print(f"User '{username}' not found. Creating a new user.")
        user = User(username=username, password_hash="mock_password_hash")  # Replace with a hashed password if necessary
        db.session.add(user)
        db.session.commit()
    else:
        print(f"User '{username}' found. Adding data to this user.")
    return user

def create_or_get_muscle_group(name):
    muscle_group = MuscleGroup.query.filter_by(name=name).first()
    if not muscle_group:
        muscle_group = MuscleGroup(name=name)
        db.session.add(muscle_group)
        db.session.commit()
    return muscle_group

def create_or_get_movement(name, muscle_groups):
    movement = Movement.query.filter_by(name=name).first()
    if not movement:
        movement = Movement(name=name)
        db.session.add(movement)
        db.session.commit()

        for group_name, impact in muscle_groups.items():
            muscle_group = create_or_get_muscle_group(group_name)
            mmg = MovementMuscleGroup(
                movement_id=movement.id,
                muscle_group_id=muscle_group.id,
                impact=impact
            )
            db.session.add(mmg)
            db.session.commit()
    return movement

def create_mock_workouts(user, num_workouts=30):
    for _ in range(num_workouts):
        # Generate a random date in the past 6 months
        completion_date = datetime.now() - timedelta(days=random.randint(1, 60))

        # Create a workout
        workout = Workout(
            name=f"Mock Workout {completion_date.strftime('%Y-%m-%d')}",
            date=completion_date.date(),
            status="completed",
            user_id=user.id,
            completion_date=completion_date.date()
        )
        db.session.add(workout)
        db.session.commit()

        # Add movements to the workout
        for _ in range(random.randint(3, 6)):  # 3-6 movements per workout
            movement_data = random.choice(MOVEMENTS)
            movement = create_or_get_movement(movement_data["name"], movement_data["muscle_groups"])

            wm = WorkoutMovement(
                workout_id=workout.id,
                movement_id=movement.id,
                sets=random.randint(3, 5),  # 3-5 sets
                reps_per_set=random.randint(8, 12),  # 8-12 reps per set
                weight=random.uniform(20, 100),  # 20-100 kg
                done=True
            )
            db.session.add(wm)

        db.session.commit()

def populate_mock_data():
    user = get_or_create_user(username="jimi")
    create_mock_workouts(user)

if __name__ == "__main__":
    from app import app  # Ensure this imports your Flask app
    with app.app_context():
        populate_mock_data()
        print("Mock data populated successfully!")

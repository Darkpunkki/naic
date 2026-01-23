from datetime import datetime
from decimal import Decimal

from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models import (
    User,
    Workout,
    Movement,
    MuscleGroup,
    MovementMuscleGroup,
    WorkoutMovement,
    Set,
    Rep,
    Weight,
)


MUSCLE_GROUPS = [
    "Chest",
    "Back",
    "Biceps",
    "Triceps",
    "Shoulders",
    "Quadriceps",
    "Hamstrings",
    "Calves",
    "Glutes",
    "Core",
    "Obliques",
    "Lower Back",
    "Forearms",
    "Neck",
    "Hip Flexors",
    "Adductors",
    "Abductors",
]


def create_user(
    username="testuser",
    email=None,
    password_hash=None,
    sex=None,
    bodyweight=None,
    gym_experience=None,
):
    user = User(
        username=username,
        email=email or f"{username}@example.com",
        password_hash=password_hash or generate_password_hash("password123"),
        sex=sex,
        bodyweight=bodyweight,
        gym_experience=gym_experience,
    )
    db.session.add(user)
    db.session.commit()
    return user


def create_workout(user, workout_name="Test Workout", workout_date=None, is_completed=None):
    workout = Workout(
        user=user,
        workout_name=workout_name,
        workout_date=workout_date or datetime.utcnow(),
    )
    if is_completed is not None:
        workout.is_completed = is_completed
    db.session.add(workout)
    db.session.commit()
    return workout


def create_movement_with_muscle_groups(movement_name="Test Movement", muscle_groups=None):
    movement = Movement(movement_name=movement_name)
    db.session.add(movement)
    if muscle_groups:
        for mg_name, pct in muscle_groups:
            mg = MuscleGroup(muscle_group_name=mg_name)
            mmg = MovementMuscleGroup(
                movement=movement,
                muscle_group=mg,
                target_percentage=pct,
            )
            db.session.add_all([mg, mmg])
    db.session.commit()
    return movement


def create_workout_movement_with_sets(
    user_bodyweight=Decimal("80.0"),
    muscle_groups=(("Chest", 100),),
    reps_per_set=10,
    weight_value=50,
    is_bodyweight=False,
    set_count=1,
):
    user = create_user(bodyweight=user_bodyweight)
    workout = create_workout(user)
    movement = create_movement_with_muscle_groups(muscle_groups=muscle_groups)
    wm = WorkoutMovement(workout=workout, movement=movement)
    db.session.add(wm)

    for index in range(set_count):
        workout_set = Set(workout_movement=wm, set_order=index + 1)
        rep = Rep(set=workout_set, rep_count=reps_per_set)
        weight = Weight(
            set=workout_set,
            weight_value=Decimal(str(weight_value)),
            is_bodyweight=is_bodyweight,
        )
        db.session.add_all([workout_set, rep, weight])

    db.session.commit()
    return user, workout, movement, wm


# --- User Model ---

def test_create_user_with_valid_data(app):
    user = create_user(username="validuser", email="valid@example.com")
    assert user.user_id is not None

    fetched = User.query.filter_by(username="validuser").first()
    assert fetched is not None
    assert fetched.email == "valid@example.com"


def test_user_password_hashing(app):
    password = "super-secret"
    hashed = generate_password_hash(password)
    user = create_user(username="hashuser", password_hash=hashed)

    assert check_password_hash(user.password_hash, password) is True
    assert check_password_hash(user.password_hash, "wrong") is False


def test_user_profile_fields_store_correctly(app):
    user = create_user(
        username="profileuser",
        sex="female",
        bodyweight=Decimal("65.5"),
        gym_experience="intermediate",
    )
    fetched = User.query.get(user.user_id)

    assert fetched.sex == "female"
    assert float(fetched.bodyweight) == 65.5
    assert fetched.gym_experience == "intermediate"


# --- Workout Model ---

def test_create_workout_with_required_fields(app):
    user = create_user(username="workoutuser")
    workout = create_workout(user, workout_name="Leg Day")

    assert workout.workout_id is not None
    assert workout.workout_name == "Leg Day"
    assert workout.user_id == user.user_id


def test_workout_user_relationship(app):
    user = create_user(username="relationshipuser")
    workout = create_workout(user)

    assert workout.user == user
    assert len(user.workouts) == 1
    assert user.workouts[0].workout_id == workout.workout_id


def test_workout_default_is_completed_false(app):
    user = create_user(username="defaultuser")
    workout = create_workout(user)

    assert workout.is_completed is False


def test_workout_cascade_delete_removes_workout_movements(app):
    user = create_user(username="cascadeuser")
    workout = create_workout(user)
    movement = create_movement_with_muscle_groups(movement_name="Bench Press")
    wm = WorkoutMovement(workout=workout, movement=movement)
    db.session.add(wm)
    db.session.commit()

    db.session.delete(workout)
    db.session.commit()

    assert WorkoutMovement.query.count() == 0


# --- WorkoutMovement Model ---

def test_create_workout_movement_link(app):
    user = create_user(username="linkuser")
    workout = create_workout(user)
    movement = create_movement_with_muscle_groups(movement_name="Squat")

    wm = WorkoutMovement(workout=workout, movement=movement)
    db.session.add(wm)
    db.session.commit()

    assert wm.workout_id == workout.workout_id
    assert wm.movement_id == movement.movement_id
    assert wm.workout == workout
    assert wm.movement == movement


def test_calculate_muscle_group_impact_structure(app):
    _, _, _, wm = create_workout_movement_with_sets(
        muscle_groups=(("Chest", 70), ("Triceps", 30)),
        reps_per_set=8,
        weight_value=40,
        is_bodyweight=False,
    )

    impacts = wm.calculate_muscle_group_impact()
    assert set(impacts.keys()) == {"Chest", "Triceps"}
    assert all(isinstance(value, float) for value in impacts.values())


def test_calculate_muscle_group_impact_single_group(app):
    _, _, _, wm = create_workout_movement_with_sets(
        muscle_groups=(("Chest", 100),),
        reps_per_set=10,
        weight_value=50,
        is_bodyweight=False,
    )

    impacts = wm.calculate_muscle_group_impact()
    assert impacts["Chest"] == 10 * 60


def test_calculate_muscle_group_impact_split_percentages(app):
    _, _, _, wm = create_workout_movement_with_sets(
        muscle_groups=(("Chest", 70), ("Triceps", 30)),
        reps_per_set=10,
        weight_value=100,
        is_bodyweight=False,
    )

    impacts = wm.calculate_muscle_group_impact()
    assert impacts["Chest"] == 770
    assert impacts["Triceps"] == 330


def test_calculate_muscle_group_impact_bodyweight(app):
    _, _, _, wm = create_workout_movement_with_sets(
        user_bodyweight=Decimal("80.0"),
        muscle_groups=(("Core", 100),),
        reps_per_set=10,
        weight_value=0,
        is_bodyweight=True,
    )

    impacts = wm.calculate_muscle_group_impact()
    assert impacts["Core"] == 300


def test_calculate_muscle_group_impact_weighted(app):
    _, _, _, wm = create_workout_movement_with_sets(
        user_bodyweight=Decimal("80.0"),
        muscle_groups=(("Back", 100),),
        reps_per_set=10,
        weight_value=40,
        is_bodyweight=False,
    )

    impacts = wm.calculate_muscle_group_impact()
    assert impacts["Back"] == 500


def test_calculate_muscle_group_impact_multiple_sets(app):
    _, _, _, wm = create_workout_movement_with_sets(
        muscle_groups=(("Glutes", 100),),
        reps_per_set=10,
        weight_value=50,
        is_bodyweight=False,
        set_count=2,
    )

    impacts = wm.calculate_muscle_group_impact()
    assert impacts["Glutes"] == 1200


def test_workout_movement_cascade_delete_sets_reps_weights(app):
    _, _, _, wm = create_workout_movement_with_sets(
        muscle_groups=(("Shoulders", 100),),
        reps_per_set=10,
        weight_value=20,
        is_bodyweight=False,
    )

    db.session.delete(wm)
    db.session.commit()

    assert Set.query.count() == 0
    assert Rep.query.count() == 0
    assert Weight.query.count() == 0


# --- Movement Model ---

def test_create_movement_with_name(app):
    movement = Movement(movement_name="Deadlift")
    db.session.add(movement)
    db.session.commit()

    assert movement.movement_id is not None
    assert movement.movement_name == "Deadlift"


def test_movement_muscle_group_relationship(app):
    movement = Movement(movement_name="Bench Press")
    mg = MuscleGroup(muscle_group_name="Chest")
    mmg = MovementMuscleGroup(movement=movement, muscle_group=mg, target_percentage=75)
    db.session.add_all([movement, mg, mmg])
    db.session.commit()

    assert movement.muscle_groups[0].muscle_group.muscle_group_name == "Chest"
    assert mg.movement_muscle_groups[0].movement.movement_name == "Bench Press"


# --- MuscleGroup Model ---

def test_all_17_muscle_groups_can_be_created(app):
    for name in MUSCLE_GROUPS:
        db.session.add(MuscleGroup(muscle_group_name=name))
    db.session.commit()

    assert MuscleGroup.query.count() == 17


def test_movement_muscle_group_target_percentage(app):
    movement = Movement(movement_name="Row")
    mg = MuscleGroup(muscle_group_name="Back")
    mmg = MovementMuscleGroup(movement=movement, muscle_group=mg, target_percentage=60)
    db.session.add_all([movement, mg, mmg])
    db.session.commit()

    fetched = MovementMuscleGroup.query.first()
    assert fetched.target_percentage == 60


# --- Set / Rep / Weight Models ---

def test_create_set_with_set_order(app):
    user = create_user(username="setuser")
    workout = create_workout(user)
    movement = create_movement_with_muscle_groups(movement_name="Lunge")
    wm = WorkoutMovement(workout=workout, movement=movement)
    db.session.add(wm)
    db.session.commit()

    workout_set = Set(workout_movement=wm, set_order=2)
    db.session.add(workout_set)
    db.session.commit()

    assert workout_set.set_order == 2


def test_rep_stores_rep_count(app):
    user = create_user(username="repuser")
    workout = create_workout(user)
    movement = create_movement_with_muscle_groups(movement_name="Curl")
    wm = WorkoutMovement(workout=workout, movement=movement)
    db.session.add(wm)
    db.session.commit()

    workout_set = Set(workout_movement=wm, set_order=1)
    rep = Rep(set=workout_set, rep_count=12)
    db.session.add_all([workout_set, rep])
    db.session.commit()

    fetched = Rep.query.first()
    assert fetched.rep_count == 12


def test_weight_stores_value_and_bodyweight_flag(app):
    user = create_user(username="weightuser")
    workout = create_workout(user)
    movement = create_movement_with_muscle_groups(movement_name="Press")
    wm = WorkoutMovement(workout=workout, movement=movement)
    db.session.add(wm)
    db.session.commit()

    workout_set = Set(workout_movement=wm, set_order=1)
    weight = Weight(set=workout_set, weight_value=Decimal("22.5"), is_bodyweight=True)
    db.session.add_all([workout_set, weight])
    db.session.commit()

    fetched = Weight.query.first()
    assert float(fetched.weight_value) == 22.5
    assert fetched.is_bodyweight is True

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# -----------------------------
# USERS
# -----------------------------
class User(db.Model):
    __tablename__ = 'Users'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    sex = db.Column(db.String(10))
    bodyweight = db.Column(db.Numeric(5, 2))
    gym_experience = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationships
    workouts = db.relationship('Workout', back_populates='user')

    def __repr__(self):
        return f"<User {self.username}>"


# -----------------------------
# USER GROUPS (Optional in code if you're actively using them)
# -----------------------------
class UserGroup(db.Model):
    __tablename__ = 'UserGroups'
    group_id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False)
    group_description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationship example if you want to link to memberships
    memberships = db.relationship('UserGroupMembership', back_populates='group')

    def __repr__(self):
        return f"<UserGroup {self.group_name}>"


class UserGroupMembership(db.Model):
    __tablename__ = 'UserGroupMembership'
    membership_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('UserGroups.group_id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='user_groups')
    group = db.relationship('UserGroup', back_populates='memberships')

    def __repr__(self):
        return f"<UserGroupMembership user_id={self.user_id} group_id={self.group_id}>"


# -----------------------------
# MUSCLE GROUPS
# -----------------------------
class MuscleGroup(db.Model):
    __tablename__ = 'MuscleGroups'
    muscle_group_id = db.Column(db.Integer, primary_key=True)
    muscle_group_name = db.Column(db.String(100), nullable=False, unique=True)
    muscle_group_description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationship with MovementMuscleGroup
    movement_muscle_groups = db.relationship('MovementMuscleGroup', back_populates='muscle_group')

    def __repr__(self):
        return f"<MuscleGroup {self.muscle_group_name}>"


# -----------------------------
# MOVEMENTS
# -----------------------------
class Movement(db.Model):
    __tablename__ = 'Movements'
    movement_id = db.Column(db.Integer, primary_key=True)
    movement_name = db.Column(db.String(100), nullable=False)
    movement_description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationship to the MovementMuscleGroup join table
    muscle_groups = db.relationship('MovementMuscleGroup', back_populates='movement')

    # Relationship to WorkoutMovement
    workout_movements = db.relationship('WorkoutMovement', back_populates='movement')

    def __repr__(self):
        return f"<Movement {self.movement_name}>"


class MovementMuscleGroup(db.Model):
    __tablename__ = 'MovementMuscleGroup'
    movement_muscle_group_id = db.Column(db.Integer, primary_key=True)
    movement_id = db.Column(db.Integer, db.ForeignKey('Movements.movement_id'), nullable=False)
    muscle_group_id = db.Column(db.Integer, db.ForeignKey('MuscleGroups.muscle_group_id'), nullable=False)
    target_percentage = db.Column(db.Integer, nullable=False)  # e.g., 70 for 70%

    # Relationships
    movement = db.relationship('Movement', back_populates='muscle_groups')
    muscle_group = db.relationship('MuscleGroup', back_populates='movement_muscle_groups')

    def __repr__(self):
        return (
            f"<MovementMuscleGroup movement_id={self.movement_id}, "
            f"muscle_group_id={self.muscle_group_id}, target={self.target_percentage}%>"
        )


# -----------------------------
# WORKOUTS
# -----------------------------
class Workout(db.Model):
    __tablename__ = 'Workouts'
    workout_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    workout_name = db.Column(db.String(100), nullable=False)
    workout_date = db.Column(db.DateTime, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationship back to the user
    user = db.relationship('User', back_populates='workouts')

    # Relationship to WorkoutMovement
    workout_movements = db.relationship('WorkoutMovement', back_populates='workout')

    def __repr__(self):
        return f"<Workout {self.workout_name} on {self.workout_date}>"


# -----------------------------
# WORKOUT-MOVEMENT JOIN
# -----------------------------
class WorkoutMovement(db.Model):
    __tablename__ = 'WorkoutMovement'
    workout_movement_id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('Workouts.workout_id'), nullable=False)
    movement_id = db.Column(db.Integer, db.ForeignKey('Movements.movement_id'), nullable=False)

    # Relationships
    workout = db.relationship('Workout', back_populates='workout_movements')
    movement = db.relationship('Movement', back_populates='workout_movements')

    # Each WorkoutMovement can have multiple sets (with their own reps & weights)
    sets = db.relationship('Set', back_populates='workout_movement', cascade='all, delete-orphan')

    def calculate_muscle_group_impact(self):
        """
        Calculate total impact on each muscle group, factoring in:
          - Reps from the Reps table
          - Weight from the Weights table
          - Whether the exercise is bodyweight (use user’s bodyweight or 0)
          - The movement's target_percentage for each muscle group
        """
        impacts = {}

        # If the user’s bodyweight isn't set, default to 1 to avoid errors
        user_bodyweight = self.workout.user.bodyweight or 1

        # Initialize all relevant muscle groups in the dictionary
        for mg_assoc in self.movement.muscle_groups:
            mg_name = mg_assoc.muscle_group.muscle_group_name
            impacts[mg_name] = 0.0

        # Go through each set in this WorkoutMovement
        for single_set in self.sets:
            # Sum up total reps from the Reps table
            total_reps = sum(rep.rep_count for rep in single_set.reps)

            # For each recorded weight entry in this set
            for w in single_set.weights:
                # If it's bodyweight, use the user's bodyweight; otherwise, use the weight_value
                actual_weight = user_bodyweight if w.is_bodyweight else w.weight_value

                # For each muscle group associated with the movement
                for mg_assoc in self.movement.muscle_groups:
                    mg_name = mg_assoc.muscle_group.muscle_group_name
                    # Convert target_percentage to a 0–1 float (e.g. 70 -> 0.70)
                    muscle_impact_multiplier = mg_assoc.target_percentage / 100.0

                    # Accumulate impact
                    impacts[mg_name] += muscle_impact_multiplier * total_reps * float(actual_weight)

        return impacts

    def __repr__(self):
        return f"<WorkoutMovement {self.workout_movement_id}: workout={self.workout_id}, movement={self.movement_id}>"


# -----------------------------
# SETS
# -----------------------------
class Set(db.Model):
    __tablename__ = 'Sets'
    set_id = db.Column(db.Integer, primary_key=True)
    workout_movement_id = db.Column(db.Integer, db.ForeignKey('WorkoutMovement.workout_movement_id'), nullable=False)
    set_order = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationship back to WorkoutMovement
    workout_movement = db.relationship('WorkoutMovement', back_populates='sets')

    # Each set can have multiple entries for Reps & Weights
    reps = db.relationship('Rep', back_populates='set', cascade='all, delete-orphan')
    weights = db.relationship('Weight', back_populates='set', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Set {self.set_id} (order={self.set_order})>"


# -----------------------------
# REPS
# -----------------------------
class Rep(db.Model):
    __tablename__ = 'Reps'
    rep_id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey('Sets.set_id'), nullable=False)
    rep_count = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationship back to Set
    set = db.relationship('Set', back_populates='reps')

    def __repr__(self):
        return f"<Rep {self.rep_id}: set_id={self.set_id}, rep_count={self.rep_count}>"


# -----------------------------
# WEIGHTS
# -----------------------------
class Weight(db.Model):
    __tablename__ = 'Weights'
    weight_id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey('Sets.set_id'), nullable=False)
    weight_value = db.Column(db.Numeric(5, 2), nullable=False)
    is_bodyweight = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationship back to Set
    set = db.relationship('Set', back_populates='weights')

    def __repr__(self):
        return f"<Weight {self.weight_id}: set_id={self.set_id}, value={self.weight_value}, bodyweight={self.is_bodyweight}>"

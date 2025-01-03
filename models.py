from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    # Relationship with Workout
    workouts = db.relationship('Workout', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User {self.username}>"


class MuscleGroup(db.Model):
    __tablename__ = 'muscle_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    # Relationship with MovementMuscleGroup
    movement_muscle_groups = db.relationship('MovementMuscleGroup', back_populates='muscle_group')

    def __repr__(self):
        return f"<MuscleGroup {self.name}>"


class Movement(db.Model):
    __tablename__ = 'movements'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Define the relationship with back_populates to avoid conflicts
    workout_movements = db.relationship('WorkoutMovement', back_populates='movement')

    # Many-to-Many relationship with MuscleGroup via MovementMuscleGroup
    muscle_groups = db.relationship('MovementMuscleGroup', back_populates='movement')

    def __repr__(self):
        return f"<Movement {self.name}>"


class MovementMuscleGroup(db.Model):
    __tablename__ = 'movement_muscle_groups'
    id = db.Column(db.Integer, primary_key=True)
    movement_id = db.Column(db.Integer, db.ForeignKey('movements.id'), nullable=False)
    muscle_group_id = db.Column(db.Integer, db.ForeignKey('muscle_groups.id'), nullable=False)
    impact = db.Column(db.Float, nullable=False)  # Impact percentage (e.g., 60 for 60%)

    # Relationships
    movement = db.relationship('Movement', back_populates='muscle_groups')
    muscle_group = db.relationship('MuscleGroup', back_populates='movement_muscle_groups')

    def __repr__(self):
        return f"<MovementMuscleGroup Movement={self.movement_id}, MuscleGroup={self.muscle_group_id}, Impact={self.impact}>"


class Workout(db.Model):
    __tablename__ = 'workouts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='planned')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    completion_date = db.Column(db.Date, nullable=True)

    # Define the relationship with back_populates
    workout_movements = db.relationship('WorkoutMovement', back_populates='workout')
    user = db.relationship('User', back_populates='workouts')

    def __repr__(self):
        return f"<Workout {self.name} on {self.date}>"


class WorkoutMovement(db.Model):
    __tablename__ = 'workout_movements'
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.id'), nullable=False)
    movement_id = db.Column(db.Integer, db.ForeignKey('movements.id'), nullable=False)

    sets = db.Column(db.Integer, default=1)
    reps_per_set = db.Column(db.Integer, default=10)
    weight = db.Column(db.Float, default=0.0)
    done = db.Column(db.Boolean, nullable=False, default=False)

    # Define relationships
    workout = db.relationship('Workout', back_populates='workout_movements')
    movement = db.relationship('Movement', back_populates='workout_movements')

    def calculate_muscle_group_impact(self):
        """Calculate total impact on each muscle group based on the movement's data."""
        impacts = {}
        for muscle_group_assoc in self.movement.muscle_groups:
            muscle_group = muscle_group_assoc.muscle_group.name
            impact = muscle_group_assoc.impact * self.sets * self.reps_per_set * self.weight
            impacts[muscle_group] = impacts.get(muscle_group, 0) + impact
        return impacts

    def __repr__(self):
        return (
            f"<WorkoutMovement: workout={self.workout_id}, "
            f"movement={self.movement_id}, sets={self.sets}, "
            f"reps={self.reps_per_set}, weight={self.weight}, done={self.done}>"
        )
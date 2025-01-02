# models.py
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


class Movement(db.Model):
    __tablename__ = 'movements'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Define the relationship with back_populates to avoid conflicts
    workout_movements = db.relationship('WorkoutMovement', back_populates='movement')

    def __repr__(self):
        return f"<Movement {self.name}>"


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

    def __repr__(self):
        return (
            f"<WorkoutMovement: workout={self.workout_id}, "
            f"movement={self.movement_id}, sets={self.sets}, "
            f"reps={self.reps_per_set}, weight={self.weight}, done={self.done}>"
        )

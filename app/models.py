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
    workout_goal = db.Column(db.String(100))  # e.g., "muscle growth", "cardio", "strength"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Rate limiting fields for LLM API calls
    llm_requests_hour = db.Column(db.Integer, default=0)
    llm_requests_day = db.Column(db.Integer, default=0)
    llm_requests_reset_hour = db.Column(db.DateTime, nullable=True)
    llm_requests_reset_day = db.Column(db.DateTime, nullable=True)

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
    role = db.Column(db.String(20), default='member')  # 'owner', 'admin', 'member'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='user_groups')
    group = db.relationship('UserGroup', back_populates='memberships')

    def __repr__(self):
        return f"<UserGroupMembership user_id={self.user_id} group_id={self.group_id} role={self.role}>"


class GroupInvitation(db.Model):
    __tablename__ = 'GroupInvitations'
    invitation_id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('UserGroups.group_id'), nullable=False)
    inviter_user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    invitee_user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'declined'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, default=None)

    # Relationships
    group = db.relationship('UserGroup', backref='invitations')
    inviter = db.relationship('User', foreign_keys=[inviter_user_id], backref='sent_invitations')
    invitee = db.relationship('User', foreign_keys=[invitee_user_id], backref='received_invitations')

    def __repr__(self):
        return f"<GroupInvitation id={self.invitation_id} group={self.group_id} status={self.status}>"


class GroupJoinRequest(db.Model):
    """User-initiated requests to join a group."""
    __tablename__ = 'GroupJoinRequests'
    request_id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('UserGroups.group_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rejected'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, default=None)
    responded_by = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=True)

    # Relationships
    group = db.relationship('UserGroup', backref='join_requests')
    user = db.relationship('User', foreign_keys=[user_id], backref='group_join_requests')
    responder = db.relationship('User', foreign_keys=[responded_by], backref='responded_join_requests')

    def __repr__(self):
        return f"<GroupJoinRequest id={request_id} user={self.user_id} group={self.group_id} status={self.status}>"


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
    workout_group_id = db.Column(db.String(36), nullable=True)  # UUID for workouts created together
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    # Relationship back to the user
    user = db.relationship('User', back_populates='workouts')

    # Relationship to WorkoutMovement
    workout_movements = db.relationship('WorkoutMovement', back_populates='workout', cascade="all, delete-orphan")

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
        Calculate total impact on each muscle group using the scoring rules
        in app.services.stats_service. This accounts for:
          - Reps and weight per set entry
          - Bodyweight as a minor factor (if flagged)
          - Normalized muscle group percentages
        """
        from app.services.stats_service import StatsService
        return StatsService.calculate_muscle_group_impact(self)

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
    entries = db.relationship('SetEntry', back_populates='set', cascade='all, delete-orphan')

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


# -----------------------------
# SET ENTRIES (PAIRED REPS & WEIGHTS)
# -----------------------------
class SetEntry(db.Model):
    __tablename__ = 'SetEntries'
    entry_id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey('Sets.set_id'), nullable=False)
    entry_order = db.Column(db.Integer, nullable=False, default=1)
    reps = db.Column(db.Integer, nullable=False)
    weight_value = db.Column(db.Numeric(5, 2), nullable=False)
    is_bodyweight = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    set = db.relationship('Set', back_populates='entries')

    def __repr__(self):
        return (
            f"<SetEntry {self.entry_id}: set_id={self.set_id}, "
            f"order={self.entry_order}, reps={self.reps}, weight={self.weight_value}, bodyweight={self.is_bodyweight}>"
        )


# -----------------------------
# WORKOUT MUSCLE GROUP IMPACT (SUMMARY TABLE)
# -----------------------------
class WorkoutMuscleGroupImpact(db.Model):
    __tablename__ = 'WorkoutMuscleGroupImpact'
    impact_id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('Workouts.workout_id'), nullable=False)
    muscle_group_id = db.Column(db.Integer, db.ForeignKey('MuscleGroups.muscle_group_id'), nullable=False)
    total_volume = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_reps = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_sets = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=None, onupdate=datetime.utcnow)

    workout = db.relationship('Workout', backref=db.backref('muscle_group_impacts', cascade='all, delete-orphan'))
    muscle_group = db.relationship('MuscleGroup', backref='workout_impacts')

    def __repr__(self):
        return (
            f"<WorkoutMuscleGroupImpact workout_id={self.workout_id}, "
            f"muscle_group_id={self.muscle_group_id}, volume={self.total_volume}>"
        )

# leaderboard.py
from flask import Blueprint, render_template, request, session
from datetime import datetime, timedelta
from sqlalchemy import func
from app.models import db
from app.models import User, Workout, UserGroup, UserGroupMembership
from app.models import WorkoutMovement
from app.models import MuscleGroup

leaderboard_bp = Blueprint('leaderboard', __name__)


def get_user_groups(user_id):
    """Get all groups the user is a member of."""
    if not user_id:
        return []
    memberships = UserGroupMembership.query.filter_by(user_id=user_id).all()
    return [{'group_id': m.group.group_id, 'group_name': m.group.group_name} for m in memberships]


def get_group_member_ids(group_id):
    """Get all user IDs that are members of a group."""
    memberships = UserGroupMembership.query.filter_by(group_id=group_id).all()
    return [m.user_id for m in memberships]

@leaderboard_bp.route('/leaderboard/workouts_this_week')
def leaderboard_workouts_this_week():
    """
    Leaderboard #1: How many workouts each user has in the last 7 days.
    """
    start_of_week = datetime.now() - timedelta(days=7)
    group_id = request.args.get('group_id', type=int)
    user_id = session.get('user_id')
    user_groups = get_user_groups(user_id)

    query = (
        db.session.query(
            User.username,
            func.count(Workout.workout_id).label('workout_count')
        )
        .join(Workout, Workout.user_id == User.user_id)
        .filter(Workout.workout_date >= start_of_week)
        .filter(Workout.is_completed == True)
    )

    # Filter by group if specified
    if group_id:
        member_ids = get_group_member_ids(group_id)
        query = query.filter(User.user_id.in_(member_ids))

    user_workout_counts = (
        query
        .group_by(User.username)
        .order_by(func.count(Workout.workout_id).desc())
        .all()
    )

    return render_template(
        'leaderboards_workouts.html',
        user_workout_counts=user_workout_counts,
        user_groups=user_groups,
        selected_group_id=group_id,
        enumerate=enumerate
    )


@leaderboard_bp.route('/leaderboard/total_impact_this_week')
def leaderboard_total_impact_this_week():
    """
    Leaderboard #2: Sum of total muscle-group impacts for each user (past 7 days).
    Uses Python to iterate over relevant workouts and calls your existing
    wm.calculate_muscle_group_impact() for each WorkoutMovement.
    """

    start_of_week = datetime.now() - timedelta(days=7)
    group_id = request.args.get('group_id', type=int)
    user_id = session.get('user_id')
    user_groups = get_user_groups(user_id)

    # Get users to include (all or filtered by group)
    if group_id:
        member_ids = get_group_member_ids(group_id)
        all_users = User.query.filter(User.user_id.in_(member_ids)).all()
    else:
        all_users = User.query.all()

    results = []  # list of (username, total_impact)

    for user in all_users:
        # Get the user's completed workouts in the last 7 days
        user_workouts = (
            Workout.query
            .filter(Workout.user_id == user.user_id)
            .filter(Workout.workout_date >= start_of_week)
            .filter(Workout.is_completed == True)
            .all()
        )

        total_impact = 0.0
        for w in user_workouts:
            for wm in w.workout_movements:
                mg_impact_dict = wm.calculate_muscle_group_impact()  # returns { "Chest": val, "Back": val, ... }
                total_impact += sum(mg_impact_dict.values())

        results.append((user.username, total_impact))

    # Sort descending by total impact
    results.sort(key=lambda x: x[1], reverse=True)

    return render_template(
        'leaderboards_total_impact.html',
        leaderboard=results,
        user_groups=user_groups,
        selected_group_id=group_id,
        enumerate=enumerate
    )


@leaderboard_bp.route('/leaderboard/impact_per_muscle')
def leaderboard_impact_per_muscle():
    """
    Leaderboard #3: Shows each user's impact for each muscle group in the past 7 days
    (pivot table style).
    """

    start_of_week = datetime.now() - timedelta(days=7)
    group_id = request.args.get('group_id', type=int)
    user_id = session.get('user_id')
    user_groups = get_user_groups(user_id)

    # Get users to include (all or filtered by group)
    if group_id:
        member_ids = get_group_member_ids(group_id)
        all_users = User.query.filter(User.user_id.in_(member_ids)).all()
    else:
        all_users = User.query.all()

    all_muscle_groups = [mg.muscle_group_name for mg in MuscleGroup.query.all()]

    # user_muscle_impact => { username: { 'Chest': 123, 'Back': 456, ... } }
    user_muscle_impact = {}

    for user in all_users:
        # Initialize each muscle group to 0
        user_muscle_impact[user.username] = {
            mg_name: 0.0 for mg_name in all_muscle_groups
        }

        # This user's completed workouts in the last 7 days
        user_workouts = (
            Workout.query
            .filter(Workout.user_id == user.user_id)
            .filter(Workout.workout_date >= start_of_week)
            .filter(Workout.is_completed == True)
            .all()
        )

        # Accumulate impact for each muscle group
        for w in user_workouts:
            for wm in w.workout_movements:
                mg_impact_dict = wm.calculate_muscle_group_impact()
                for mg_name, impact_value in mg_impact_dict.items():
                    user_muscle_impact[user.username][mg_name] += impact_value

    return render_template(
        'leaderboards_per_muscle.html',
        all_muscle_groups=all_muscle_groups,
        user_muscle_impact=user_muscle_impact,
        user_groups=user_groups,
        selected_group_id=group_id,
        enumerate=enumerate
    )

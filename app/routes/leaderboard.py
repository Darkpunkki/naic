import math
from datetime import datetime, timedelta

import pytz
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from sqlalchemy import func

from app.models import db, User, Workout, UserGroupMembership, MuscleGroup, WorkoutMuscleGroupImpact

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


def _normalize_period(value: str) -> str:
    if not value:
        return "week"
    value = value.lower()
    if value in {"week", "weekly", "this_week"}:
        return "week"
    if value in {"month", "monthly", "this_month"}:
        return "month"
    return "all"


def _period_days(period: str) -> int:
    if period == "week":
        return 7
    if period == "month":
        return 30
    return 180


def _period_range(period: str):
    current_datetime = datetime.now(pytz.UTC)
    current_date = current_datetime.date()
    days = _period_days(period)
    start_date = current_date - timedelta(days=days - 1)

    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    end_datetime = datetime.combine(current_date, datetime.max.time()).replace(tzinfo=pytz.UTC)

    return start_datetime, end_datetime


def _balance_score(values):
    positives = [v for v in values if v > 0]
    if len(positives) <= 1:
        return 0.0
    total = sum(positives)
    proportions = [v / total for v in positives]
    entropy = -sum(p * math.log(p) for p in proportions)
    return round(entropy / math.log(len(positives)), 3)


@leaderboard_bp.route('/leaderboard')
def leaderboard_view():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    group_id = request.args.get('group_id', type=int)
    period = _normalize_period(request.args.get('period', 'week'))
    user_groups = get_user_groups(user_id)

    return render_template(
        'leaderboard.html',
        user_groups=user_groups,
        selected_group_id=group_id,
        period=period
    )


@leaderboard_bp.route('/leaderboard/data')
def leaderboard_data():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    group_id = request.args.get('group_id', type=int)
    period = _normalize_period(request.args.get('period', 'week'))
    start_dt, end_dt = _period_range(period)

    if group_id:
        # Show only members of the selected group
        member_ids = get_group_member_ids(group_id)
        users = User.query.filter(User.user_id.in_(member_ids)).all()
    else:
        # Show only users who share at least one group with current user
        user_groups = get_user_groups(user_id)
        if user_groups:
            # Get all unique user IDs from all the user's groups
            all_group_member_ids = set()
            for group in user_groups:
                group_member_ids = get_group_member_ids(group['group_id'])
                all_group_member_ids.update(group_member_ids)
            users = User.query.filter(User.user_id.in_(all_group_member_ids)).all()
        else:
            # User is not in any groups - only show themselves
            users = User.query.filter(User.user_id == user_id).all()

    user_ids = [u.user_id for u in users]
    all_muscle_groups = [mg.muscle_group_name for mg in MuscleGroup.query.order_by(MuscleGroup.muscle_group_name).all()]

    user_data = {
        u.user_id: {
            "username": u.username,
            "bodyweight": float(u.bodyweight) if u.bodyweight else 0.0,
            "workouts": 0,
            "distribution": {mg: 0.0 for mg in all_muscle_groups},
            "total_volume": 0.0,
            "relative_volume": 0.0,
            "balance": 0.0,
            "relative_distribution": {mg: 0.0 for mg in all_muscle_groups},
        }
        for u in users
    }

    if user_ids:
        rows = (
            db.session.query(
                User.user_id,
                MuscleGroup.muscle_group_name,
                func.coalesce(func.sum(WorkoutMuscleGroupImpact.total_volume), 0)
            )
            .join(Workout, Workout.workout_id == WorkoutMuscleGroupImpact.workout_id)
            .join(MuscleGroup, MuscleGroup.muscle_group_id == WorkoutMuscleGroupImpact.muscle_group_id)
            .join(User, User.user_id == Workout.user_id)
            .filter(User.user_id.in_(user_ids))
            .filter(Workout.is_completed == True)
            .filter(Workout.workout_date >= start_dt)
            .filter(Workout.workout_date <= end_dt)
            .group_by(User.user_id, MuscleGroup.muscle_group_name)
            .all()
        )

        for user_id, mg_name, volume in rows:
            user_data[user_id]["distribution"][mg_name] = float(volume or 0)

        workout_counts = (
            db.session.query(User.user_id, func.count(Workout.workout_id))
            .join(Workout, Workout.user_id == User.user_id)
            .filter(User.user_id.in_(user_ids))
            .filter(Workout.is_completed == True)
            .filter(Workout.workout_date >= start_dt)
            .filter(Workout.workout_date <= end_dt)
            .group_by(User.user_id)
            .all()
        )
        for user_id, count in workout_counts:
            user_data[user_id]["workouts"] = int(count)

    for entry in user_data.values():
        total_volume = sum(entry["distribution"].values())
        bodyweight = (entry.get("bodyweight") or 0) if "bodyweight" in entry else 0
        bodyweight = bodyweight if bodyweight > 0 else 1.0
        entry["total_volume"] = round(total_volume, 2)
        entry["relative_volume"] = round(total_volume / bodyweight, 2)
        entry["balance"] = _balance_score(list(entry["distribution"].values()))
        entry["relative_distribution"] = {
            mg: round(value / bodyweight, 2)
            for mg, value in entry["distribution"].items()
        }

    users_payload = list(user_data.values())
    for entry in users_payload:
        entry.pop("bodyweight", None)
    users_payload.sort(key=lambda u: u["total_volume"], reverse=True)

    group_avg = {
        "total_volume": 0.0,
        "relative_volume": 0.0,
        "distribution": {mg: 0.0 for mg in all_muscle_groups},
    }
    if users_payload:
        count = len(users_payload)
        group_avg["total_volume"] = round(sum(u["total_volume"] for u in users_payload) / count, 2)
        group_avg["relative_volume"] = round(sum(u["relative_volume"] for u in users_payload) / count, 2)
        for mg in all_muscle_groups:
            group_avg["distribution"][mg] = round(
                sum(u["distribution"][mg] for u in users_payload) / count, 2
            )

    return jsonify({
        "period": period,
        "range": {
            "start": start_dt.strftime('%Y-%m-%d'),
            "end": end_dt.strftime('%Y-%m-%d'),
        },
        "muscle_groups": all_muscle_groups,
        "users": users_payload,
        "group_averages": group_avg,
    })


@leaderboard_bp.route('/leaderboard/workouts_this_week')
def leaderboard_workouts_this_week():
    return redirect(url_for('leaderboard.leaderboard_view'))


@leaderboard_bp.route('/leaderboard/total_impact_this_week')
def leaderboard_total_impact_this_week():
    return redirect(url_for('leaderboard.leaderboard_view'))


@leaderboard_bp.route('/leaderboard/impact_per_muscle')
def leaderboard_impact_per_muscle():
    return redirect(url_for('leaderboard.leaderboard_view'))

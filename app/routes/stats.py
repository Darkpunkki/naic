from datetime import datetime, timedelta

import pytz
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from sqlalchemy import func

from app.models import db, Workout, MuscleGroup, WorkoutMuscleGroupImpact

stats_bp = Blueprint('stats_bp', __name__)


def _normalize_period(value: str) -> str:
    if not value:
        return "all"
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

    previous_end_date = start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=days - 1)
    previous_start = datetime.combine(previous_start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    previous_end = datetime.combine(previous_end_date, datetime.max.time()).replace(tzinfo=pytz.UTC)

    return start_datetime, end_datetime, previous_start, previous_end


def _query_muscle_totals(user_id, start_dt, end_dt):
    rows = (
        db.session.query(
            MuscleGroup.muscle_group_name,
            func.coalesce(func.sum(WorkoutMuscleGroupImpact.total_volume), 0)
        )
        .join(Workout, Workout.workout_id == WorkoutMuscleGroupImpact.workout_id)
        .join(MuscleGroup, MuscleGroup.muscle_group_id == WorkoutMuscleGroupImpact.muscle_group_id)
        .filter(Workout.user_id == user_id)
        .filter(Workout.is_completed == True)
        .filter(Workout.workout_date >= start_dt)
        .filter(Workout.workout_date <= end_dt)
        .group_by(MuscleGroup.muscle_group_name)
        .all()
    )
    return {name: float(total or 0) for name, total in rows}


def _query_total_series(user_id, start_dt, end_dt):
    rows = (
        db.session.query(
            func.date(Workout.workout_date).label("workout_day"),
            func.coalesce(func.sum(WorkoutMuscleGroupImpact.total_volume), 0)
        )
        .join(Workout, Workout.workout_id == WorkoutMuscleGroupImpact.workout_id)
        .filter(Workout.user_id == user_id)
        .filter(Workout.is_completed == True)
        .filter(Workout.workout_date >= start_dt)
        .filter(Workout.workout_date <= end_dt)
        .group_by(func.date(Workout.workout_date))
        .order_by(func.date(Workout.workout_date))
        .all()
    )
    def _format_day(day):
        return day.strftime("%Y-%m-%d") if hasattr(day, "strftime") else str(day)

    return [
        {"date": _format_day(day), "volume": float(total or 0)}
        for day, total in rows
    ]


def _build_changes(current_values, previous_values):
    changes = []
    all_keys = set(current_values.keys()) | set(previous_values.keys())
    for key in all_keys:
        current_val = current_values.get(key, 0.0)
        previous_val = previous_values.get(key, 0.0)
        delta = current_val - previous_val
        if previous_val > 0:
            pct = (delta / previous_val) * 100.0
            status = "up" if delta > 0 else "down" if delta < 0 else "flat"
        else:
            pct = None
            status = "new" if current_val > 0 else "flat"
        changes.append({
            "muscle": key,
            "current": round(current_val, 2),
            "previous": round(previous_val, 2),
            "delta": round(delta, 2),
            "pct": None if pct is None else round(pct, 2),
            "status": status,
        })
    changes.sort(key=lambda item: abs(item["delta"]), reverse=True)
    return changes


@stats_bp.route('/historical_data/<muscle_group>', methods=['GET'])
def historical_data(muscle_group):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    current_datetime = datetime.now(pytz.UTC)
    current_date = current_datetime.date()
    historical_start_date = current_date - timedelta(days=180)

    start_datetime = datetime.combine(historical_start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    end_datetime = datetime.combine(current_date, datetime.max.time()).replace(tzinfo=pytz.UTC)

    mg = MuscleGroup.query.filter_by(muscle_group_name=muscle_group).first()
    if not mg:
        return jsonify([])

    rows = (
        db.session.query(
            func.date(Workout.workout_date).label("workout_day"),
            func.coalesce(func.sum(WorkoutMuscleGroupImpact.total_volume), 0)
        )
        .join(Workout, Workout.workout_id == WorkoutMuscleGroupImpact.workout_id)
        .filter(Workout.user_id == user_id)
        .filter(Workout.is_completed == True)
        .filter(WorkoutMuscleGroupImpact.muscle_group_id == mg.muscle_group_id)
        .filter(Workout.workout_date >= start_datetime)
        .filter(Workout.workout_date <= end_datetime)
        .group_by(func.date(Workout.workout_date))
        .order_by(func.date(Workout.workout_date))
        .all()
    )

    def _format_day(day):
        return day.strftime("%Y-%m-%d") if hasattr(day, "strftime") else str(day)

    data = [
        {"date": _format_day(day), "volume": float(total or 0)}
        for day, total in rows
    ]
    return jsonify(data)


@stats_bp.route('/stats', methods=['GET'])
def stats():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    period = _normalize_period(request.args.get('period') or request.args.get('time_filter') or 'all')
    return render_template('stats.html', period=period)


@stats_bp.route('/stats/data', methods=['GET'])
def stats_data():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    period = _normalize_period(request.args.get('period') or request.args.get('time_filter') or 'all')
    current_start, current_end, previous_start, previous_end = _period_range(period)

    current_values = _query_muscle_totals(user_id, current_start, current_end)
    previous_values = _query_muscle_totals(user_id, previous_start, previous_end)

    changes = _build_changes(current_values, previous_values)
    series = _query_total_series(user_id, current_start, current_end)

    return jsonify({
        "period": period,
        "range": {
            "start": current_start.strftime("%Y-%m-%d"),
            "end": current_end.strftime("%Y-%m-%d"),
        },
        "totals_by_muscle": current_values,
        "changes": changes,
        "series": series,
    })

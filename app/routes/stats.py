from datetime import datetime, timedelta, date
import csv
import io

import pytz
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, Response
from sqlalchemy import func

from app.models import (
    db,
    Workout,
    MuscleGroup,
    WorkoutMuscleGroupImpact,
    Movement,
    MovementMuscleGroup,
    MovementDailySummary,
    MuscleGroupDailySummary,
    WorkoutSessionSummary,
    WorkoutMovementStats,
    PersonalRecord,
)
from app.services.stats_v2_service import StatsV2Service
from app.services.feedback_service import MUSCLE_PAIRS

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


def _period_dates(period: str) -> tuple[date, date]:
    current_datetime = datetime.now(pytz.UTC)
    current_date = current_datetime.date()
    days = _period_days(period)
    start_date = current_date - timedelta(days=days - 1)
    return start_date, current_date


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


def _query_muscle_totals_v2(user_id, start_date, end_date):
    rows = (
        db.session.query(
            MuscleGroup.muscle_group_name,
            func.coalesce(func.sum(MuscleGroupDailySummary.total_volume), 0)
        )
        .join(MuscleGroup, MuscleGroup.muscle_group_id == MuscleGroupDailySummary.muscle_group_id)
        .filter(MuscleGroupDailySummary.user_id == user_id)
        .filter(MuscleGroupDailySummary.summary_date >= start_date)
        .filter(MuscleGroupDailySummary.summary_date <= end_date)
        .group_by(MuscleGroup.muscle_group_name)
        .all()
    )
    return {name: float(total or 0) for name, total in rows}


def _query_total_series_v2(user_id, start_date, end_date):
    rows = (
        db.session.query(
            MuscleGroupDailySummary.summary_date,
            func.coalesce(func.sum(MuscleGroupDailySummary.total_volume), 0)
        )
        .filter(MuscleGroupDailySummary.user_id == user_id)
        .filter(MuscleGroupDailySummary.summary_date >= start_date)
        .filter(MuscleGroupDailySummary.summary_date <= end_date)
        .group_by(MuscleGroupDailySummary.summary_date)
        .order_by(MuscleGroupDailySummary.summary_date)
        .all()
    )

    return [
        {"date": day.strftime("%Y-%m-%d"), "volume": float(total or 0)}
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

    v2_rows = (
        db.session.query(
            MuscleGroupDailySummary.summary_date,
            func.coalesce(func.sum(MuscleGroupDailySummary.total_volume), 0)
        )
        .filter(MuscleGroupDailySummary.user_id == user_id)
        .filter(MuscleGroupDailySummary.muscle_group_id == mg.muscle_group_id)
        .filter(MuscleGroupDailySummary.summary_date >= historical_start_date)
        .filter(MuscleGroupDailySummary.summary_date <= current_date)
        .group_by(MuscleGroupDailySummary.summary_date)
        .order_by(MuscleGroupDailySummary.summary_date)
        .all()
    )

    if v2_rows:
        data = [
            {"date": day.strftime("%Y-%m-%d"), "volume": float(total or 0)}
            for day, total in v2_rows
        ]
        return jsonify(data)

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
    current_start_date, current_end_date = _period_dates(period)
    days = _period_days(period)
    previous_end_date = current_start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=days - 1)

    v2_available = (
        db.session.query(MuscleGroupDailySummary)
        .filter(MuscleGroupDailySummary.user_id == user_id)
        .filter(MuscleGroupDailySummary.summary_date >= current_start_date)
        .limit(1)
        .count() > 0
    )

    if v2_available:
        current_values = _query_muscle_totals_v2(user_id, current_start_date, current_end_date)
        previous_values = _query_muscle_totals_v2(user_id, previous_start_date, previous_end_date)
        series = _query_total_series_v2(user_id, current_start_date, current_end_date)
    else:
        current_values = _query_muscle_totals(user_id, current_start, current_end)
        previous_values = _query_muscle_totals(user_id, previous_start, previous_end)
        series = _query_total_series(user_id, current_start, current_end)

    changes = _build_changes(current_values, previous_values)

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


@stats_bp.route('/stats/overview', methods=['GET'])
def stats_overview():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    period = _normalize_period(request.args.get('period') or 'all')
    cache_key = f"user:{user_id}:overview:{period}"
    cached = StatsV2Service._cache_get(cache_key)
    if cached:
        return jsonify(cached)

    start_date, end_date = _period_dates(period)
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=pytz.UTC)
    days = _period_days(period)

    sessions = (
        WorkoutSessionSummary.query
        .filter(WorkoutSessionSummary.user_id == user_id)
        .filter(WorkoutSessionSummary.workout_date >= start_dt)
        .filter(WorkoutSessionSummary.workout_date <= end_dt)
        .all()
    )

    total_volume = sum(float(s.total_volume or 0) for s in sessions)
    total_tonnage = sum(float(s.total_tonnage or 0) for s in sessions)
    total_reps = sum(float(s.total_reps or 0) for s in sessions)
    total_sets = sum(int(s.total_sets or 0) for s in sessions)
    completed_sets = sum(int(s.completed_sets or 0) for s in sessions)
    skipped_sets = sum(int(s.skipped_sets or 0) for s in sessions)
    avg_rpe_values = [float(s.avg_rpe) for s in sessions if s.avg_rpe is not None]
    avg_rest_values = [float(s.avg_rest_seconds) for s in sessions if s.avg_rest_seconds is not None]
    duration_values = [int(s.duration_seconds) for s in sessions if s.duration_seconds is not None]

    avg_per_day = total_volume / days if days else 0.0
    completion_rate = completed_sets / (completed_sets + skipped_sets) if (completed_sets + skipped_sets) else 0.0

    top_movement_row = (
        db.session.query(
            Movement.movement_name,
            func.coalesce(func.sum(MovementDailySummary.total_volume), 0)
        )
        .join(Movement, Movement.movement_id == MovementDailySummary.movement_id)
        .filter(MovementDailySummary.user_id == user_id)
        .filter(MovementDailySummary.summary_date >= start_date)
        .filter(MovementDailySummary.summary_date <= end_date)
        .group_by(Movement.movement_name)
        .order_by(func.coalesce(func.sum(MovementDailySummary.total_volume), 0).desc())
        .first()
    )
    top_movement = {
        "name": top_movement_row[0],
        "volume": float(top_movement_row[1] or 0),
    } if top_movement_row else None

    top_muscle_row = (
        db.session.query(
            MuscleGroup.muscle_group_name,
            func.coalesce(func.sum(MuscleGroupDailySummary.total_volume), 0)
        )
        .join(MuscleGroup, MuscleGroup.muscle_group_id == MuscleGroupDailySummary.muscle_group_id)
        .filter(MuscleGroupDailySummary.user_id == user_id)
        .filter(MuscleGroupDailySummary.summary_date >= start_date)
        .filter(MuscleGroupDailySummary.summary_date <= end_date)
        .group_by(MuscleGroup.muscle_group_name)
        .order_by(func.coalesce(func.sum(MuscleGroupDailySummary.total_volume), 0).desc())
        .first()
    )
    top_muscle = {
        "name": top_muscle_row[0],
        "volume": float(top_muscle_row[1] or 0),
    } if top_muscle_row else None

    workout_dates = sorted({s.workout_date.date() for s in sessions if s.workout_date})
    streak = 0
    cursor = end_date
    while cursor in workout_dates:
        streak += 1
        cursor = cursor - timedelta(days=1)

    payload = {
        "period": period,
        "range": {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d")},
        "workouts": len(sessions),
        "total_volume": round(total_volume, 2),
        "total_tonnage": round(total_tonnage, 2),
        "total_reps": round(total_reps, 2),
        "total_sets": total_sets,
        "avg_per_day": round(avg_per_day, 2),
        "completion_rate": round(completion_rate, 3),
        "avg_rpe": round(sum(avg_rpe_values) / len(avg_rpe_values), 2) if avg_rpe_values else None,
        "avg_rest_seconds": round(sum(avg_rest_values) / len(avg_rest_values), 2) if avg_rest_values else None,
        "avg_duration_seconds": round(sum(duration_values) / len(duration_values), 2) if duration_values else None,
        "top_movement": top_movement,
        "top_muscle": top_muscle,
        "streak": streak,
    }

    StatsV2Service._cache_set(cache_key, payload)
    return jsonify(payload)


@stats_bp.route('/stats/movements', methods=['GET'])
def stats_movements():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    period = _normalize_period(request.args.get('period') or 'all')
    start_date, end_date = _period_dates(period)
    search = (request.args.get('search') or '').strip()
    movement_type = (request.args.get('movement_type') or '').strip()
    equipment_type = (request.args.get('equipment_type') or '').strip()
    muscle_group_id = request.args.get('muscle_group_id', type=int)
    sort_key = (request.args.get('sort') or 'volume').strip()
    limit = request.args.get('limit', type=int) or 200
    offset = request.args.get('offset', type=int) or 0

    query = (
        db.session.query(
            Movement.movement_id,
            Movement.movement_name,
            Movement.movement_type,
            Movement.equipment_type,
            func.coalesce(func.sum(MovementDailySummary.total_volume), 0).label("total_volume"),
            func.coalesce(func.sum(MovementDailySummary.total_tonnage), 0).label("total_tonnage"),
            func.coalesce(func.sum(MovementDailySummary.total_reps), 0).label("total_reps"),
            func.coalesce(func.sum(MovementDailySummary.total_sets), 0).label("total_sets"),
            func.coalesce(func.max(MovementDailySummary.e1rm_max), 0).label("e1rm_max"),
            func.coalesce(func.max(MovementDailySummary.max_weight), 0).label("max_weight"),
            func.coalesce(func.avg(MovementDailySummary.avg_rpe), 0).label("avg_rpe"),
            func.coalesce(func.avg(MovementDailySummary.avg_rest_seconds), 0).label("avg_rest_seconds"),
            func.coalesce(func.max(MovementDailySummary.summary_date), None).label("last_performed"),
            func.coalesce(func.sum(MovementDailySummary.sessions), 0).label("sessions"),
        )
        .join(Movement, Movement.movement_id == MovementDailySummary.movement_id)
        .filter(MovementDailySummary.user_id == user_id)
        .filter(MovementDailySummary.summary_date >= start_date)
        .filter(MovementDailySummary.summary_date <= end_date)
        .group_by(Movement.movement_id)
    )

    if search:
        query = query.filter(Movement.movement_name.ilike(f"%{search}%"))
    if movement_type:
        query = query.filter(Movement.movement_type == movement_type)
    if equipment_type:
        query = query.filter(Movement.equipment_type == equipment_type)
    if muscle_group_id:
        query = query.join(MovementMuscleGroup, MovementMuscleGroup.movement_id == Movement.movement_id)
        query = query.filter(MovementMuscleGroup.muscle_group_id == muscle_group_id)

    sort_map = {
        "volume": func.coalesce(func.sum(MovementDailySummary.total_volume), 0).desc(),
        "tonnage": func.coalesce(func.sum(MovementDailySummary.total_tonnage), 0).desc(),
        "e1rm": func.coalesce(func.max(MovementDailySummary.e1rm_max), 0).desc(),
        "name": Movement.movement_name.asc(),
        "last": func.coalesce(func.max(MovementDailySummary.summary_date), None).desc(),
    }
    query = query.order_by(sort_map.get(sort_key, sort_map["volume"]))

    rows = query.offset(offset).limit(limit).all()
    payload = [
        {
            "movement_id": row.movement_id,
            "movement_name": row.movement_name,
            "movement_type": row.movement_type,
            "equipment_type": row.equipment_type,
            "total_volume": float(row.total_volume or 0),
            "total_tonnage": float(row.total_tonnage or 0),
            "total_reps": float(row.total_reps or 0),
            "total_sets": float(row.total_sets or 0),
            "e1rm_max": float(row.e1rm_max or 0),
            "max_weight": float(row.max_weight or 0),
            "avg_rpe": float(row.avg_rpe) if row.avg_rpe else None,
            "avg_rest_seconds": float(row.avg_rest_seconds) if row.avg_rest_seconds else None,
            "last_performed": row.last_performed.strftime("%Y-%m-%d") if row.last_performed else None,
            "sessions": int(row.sessions or 0),
        }
        for row in rows
    ]

    return jsonify({
        "period": period,
        "range": {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d")},
        "movements": payload,
    })


@stats_bp.route('/stats/movements/<int:movement_id>/series', methods=['GET'])
def stats_movement_series(movement_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    period = _normalize_period(request.args.get('period') or 'all')
    start_date, end_date = _period_dates(period)

    series_rows = (
        MovementDailySummary.query
        .filter(MovementDailySummary.user_id == user_id)
        .filter(MovementDailySummary.movement_id == movement_id)
        .filter(MovementDailySummary.summary_date >= start_date)
        .filter(MovementDailySummary.summary_date <= end_date)
        .order_by(MovementDailySummary.summary_date)
        .all()
    )

    series = [
        {
            "date": row.summary_date.strftime("%Y-%m-%d"),
            "volume": float(row.total_volume or 0),
            "tonnage": float(row.total_tonnage or 0),
            "reps": float(row.total_reps or 0),
            "sets": float(row.total_sets or 0),
            "e1rm": float(row.e1rm_max or 0),
            "max_weight": float(row.max_weight or 0),
            "avg_rpe": float(row.avg_rpe) if row.avg_rpe else None,
            "avg_rest_seconds": float(row.avg_rest_seconds) if row.avg_rest_seconds else None,
            "sessions": int(row.sessions or 0),
        }
        for row in series_rows
    ]

    recent_sessions = (
        WorkoutMovementStats.query
        .filter(WorkoutMovementStats.user_id == user_id)
        .filter(WorkoutMovementStats.movement_id == movement_id)
        .order_by(WorkoutMovementStats.workout_date.desc())
        .limit(12)
        .all()
    )

    recent_payload = [
        {
            "workout_id": row.workout_id,
            "workout_date": row.workout_date.strftime("%Y-%m-%d") if row.workout_date else None,
            "total_volume": float(row.total_volume or 0),
            "total_tonnage": float(row.total_tonnage or 0),
            "total_reps": float(row.total_reps or 0),
            "total_sets": float(row.total_sets or 0),
            "e1rm": float(row.e1rm) if row.e1rm else None,
            "max_weight": float(row.max_weight) if row.max_weight else None,
            "avg_rpe": float(row.avg_rpe) if row.avg_rpe else None,
            "avg_rest_seconds": float(row.avg_rest_seconds) if row.avg_rest_seconds else None,
            "completion_rate": float(row.completion_rate or 0),
        }
        for row in recent_sessions
    ]

    pr_rows = (
        PersonalRecord.query
        .filter(PersonalRecord.user_id == user_id)
        .filter(PersonalRecord.movement_id == movement_id)
        .all()
    )

    prs = [
        {
            "record_type": pr.record_type,
            "value": float(pr.value or 0),
            "reps": pr.reps,
            "weight_value": float(pr.weight_value) if pr.weight_value else None,
            "achieved_at": pr.achieved_at.strftime("%Y-%m-%d") if pr.achieved_at else None,
        }
        for pr in pr_rows
    ]

    return jsonify({
        "period": period,
        "series": series,
        "recent_sessions": recent_payload,
        "prs": prs,
    })


@stats_bp.route('/stats/muscles', methods=['GET'])
def stats_muscles():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    period = _normalize_period(request.args.get('period') or 'all')
    start_date, end_date = _period_dates(period)

    rows = (
        db.session.query(
            MuscleGroup.muscle_group_name,
            func.coalesce(func.sum(MuscleGroupDailySummary.total_volume), 0)
        )
        .join(MuscleGroup, MuscleGroup.muscle_group_id == MuscleGroupDailySummary.muscle_group_id)
        .filter(MuscleGroupDailySummary.user_id == user_id)
        .filter(MuscleGroupDailySummary.summary_date >= start_date)
        .filter(MuscleGroupDailySummary.summary_date <= end_date)
        .group_by(MuscleGroup.muscle_group_name)
        .all()
    )

    distribution = [
        {"muscle": name, "volume": float(volume or 0)}
        for name, volume in sorted(rows, key=lambda x: float(x[1] or 0), reverse=True)
    ]

    volume_map = {item["muscle"]: item["volume"] for item in distribution}
    imbalances = []
    for muscle_a, muscle_b in MUSCLE_PAIRS:
        vol_a = volume_map.get(muscle_a, 0)
        vol_b = volume_map.get(muscle_b, 0)
        total = vol_a + vol_b
        if total == 0:
            continue
        ratio_a = vol_a / total
        if ratio_a > 0.65:
            imbalances.append({
                "pair": [muscle_a, muscle_b],
                "ratio": round(ratio_a, 2),
                "dominant": muscle_a,
            })
        elif ratio_a < 0.35:
            imbalances.append({
                "pair": [muscle_a, muscle_b],
                "ratio": round(ratio_a, 2),
                "dominant": muscle_b,
            })

    return jsonify({
        "period": period,
        "range": {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d")},
        "distribution": distribution,
        "imbalances": imbalances,
    })


@stats_bp.route('/stats/records', methods=['GET'])
def stats_records():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    records = (
        PersonalRecord.query
        .filter(PersonalRecord.user_id == user_id)
        .order_by(func.coalesce(PersonalRecord.updated_at, PersonalRecord.created_at).desc())
        .all()
    )

    payload = [
        {
            "movement_id": record.movement_id,
            "movement_name": record.movement.movement_name if record.movement else None,
            "record_type": record.record_type,
            "value": float(record.value or 0),
            "reps": record.reps,
            "weight_value": float(record.weight_value) if record.weight_value else None,
            "achieved_at": record.achieved_at.strftime("%Y-%m-%d") if record.achieved_at else None,
        }
        for record in records
    ]
    return jsonify({"records": payload})


@stats_bp.route('/stats/adherence', methods=['GET'])
def stats_adherence():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    period = _normalize_period(request.args.get('period') or 'all')
    start_date, end_date = _period_dates(period)
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=pytz.UTC)

    sessions = (
        WorkoutSessionSummary.query
        .filter(WorkoutSessionSummary.user_id == user_id)
        .filter(WorkoutSessionSummary.workout_date >= start_dt)
        .filter(WorkoutSessionSummary.workout_date <= end_dt)
        .all()
    )

    completed_sets = sum(int(s.completed_sets or 0) for s in sessions)
    skipped_sets = sum(int(s.skipped_sets or 0) for s in sessions)
    avg_completion = (
        sum(float(s.completion_rate or 0) for s in sessions) / len(sessions)
        if sessions else 0.0
    )
    skipped_rate = skipped_sets / (completed_sets + skipped_sets) if (completed_sets + skipped_sets) else 0.0

    movement_rows = (
        db.session.query(
            Movement.movement_name,
            func.coalesce(func.avg(WorkoutMovementStats.completion_rate), 0),
            func.coalesce(func.sum(WorkoutMovementStats.completed_sets), 0),
            func.coalesce(func.sum(WorkoutMovementStats.skipped_sets), 0),
        )
        .join(Movement, Movement.movement_id == WorkoutMovementStats.movement_id)
        .filter(WorkoutMovementStats.user_id == user_id)
        .filter(WorkoutMovementStats.workout_date >= start_dt)
        .filter(WorkoutMovementStats.workout_date <= end_dt)
        .group_by(Movement.movement_name)
        .order_by(func.coalesce(func.avg(WorkoutMovementStats.completion_rate), 0).asc())
        .limit(10)
        .all()
    )

    movement_adherence = [
        {
            "movement_name": name,
            "completion_rate": float(rate or 0),
            "completed_sets": int(completed or 0),
            "skipped_sets": int(skipped or 0),
        }
        for name, rate, completed, skipped in movement_rows
    ]

    return jsonify({
        "period": period,
        "range": {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d")},
        "workouts": len(sessions),
        "avg_completion_rate": round(avg_completion, 3),
        "skipped_set_rate": round(skipped_rate, 3),
        "movement_adherence": movement_adherence,
    })


@stats_bp.route('/stats/export/movements', methods=['GET'])
def stats_export_movements():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    period = _normalize_period(request.args.get('period') or 'all')
    start_date, end_date = _period_dates(period)

    rows = (
        db.session.query(
            MovementDailySummary.summary_date,
            Movement.movement_name,
            MovementDailySummary.total_volume,
            MovementDailySummary.total_tonnage,
            MovementDailySummary.total_reps,
            MovementDailySummary.total_sets,
            MovementDailySummary.e1rm_max,
            MovementDailySummary.max_weight,
            MovementDailySummary.avg_rpe,
            MovementDailySummary.avg_rest_seconds,
            MovementDailySummary.sessions,
        )
        .join(Movement, Movement.movement_id == MovementDailySummary.movement_id)
        .filter(MovementDailySummary.user_id == user_id)
        .filter(MovementDailySummary.summary_date >= start_date)
        .filter(MovementDailySummary.summary_date <= end_date)
        .order_by(MovementDailySummary.summary_date, Movement.movement_name)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "date",
        "movement",
        "volume",
        "tonnage",
        "reps",
        "sets",
        "e1rm",
        "max_weight",
        "avg_rpe",
        "avg_rest_seconds",
        "sessions",
    ])
    for row in rows:
        writer.writerow([
            row.summary_date.strftime("%Y-%m-%d"),
            row.movement_name,
            float(row.total_volume or 0),
            float(row.total_tonnage or 0),
            float(row.total_reps or 0),
            float(row.total_sets or 0),
            float(row.e1rm_max or 0),
            float(row.max_weight or 0),
            float(row.avg_rpe) if row.avg_rpe else "",
            float(row.avg_rest_seconds) if row.avg_rest_seconds else "",
            int(row.sessions or 0),
        ])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=movement_stats_{period}.csv"
    return response


@stats_bp.route('/stats/export/weekly', methods=['GET'])
def stats_export_weekly():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    period = _normalize_period(request.args.get('period') or 'all')
    start_date, end_date = _period_dates(period)
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=pytz.UTC)

    sessions = (
        WorkoutSessionSummary.query
        .filter(WorkoutSessionSummary.user_id == user_id)
        .filter(WorkoutSessionSummary.workout_date >= start_dt)
        .filter(WorkoutSessionSummary.workout_date <= end_dt)
        .all()
    )

    weekly = {}
    for session in sessions:
        day = session.workout_date.date()
        week_start = day - timedelta(days=day.weekday())
        key = week_start.isoformat()
        bucket = weekly.setdefault(key, {
            "week_start": week_start,
            "total_volume": 0.0,
            "total_tonnage": 0.0,
            "workouts": 0,
            "completion_rate_sum": 0.0,
            "avg_rpe_sum": 0.0,
            "avg_rpe_count": 0,
            "avg_rest_sum": 0.0,
            "avg_rest_count": 0,
            "duration_sum": 0,
            "duration_count": 0,
        })
        bucket["total_volume"] += float(session.total_volume or 0)
        bucket["total_tonnage"] += float(session.total_tonnage or 0)
        bucket["workouts"] += 1
        bucket["completion_rate_sum"] += float(session.completion_rate or 0)
        if session.avg_rpe is not None:
            bucket["avg_rpe_sum"] += float(session.avg_rpe)
            bucket["avg_rpe_count"] += 1
        if session.avg_rest_seconds is not None:
            bucket["avg_rest_sum"] += float(session.avg_rest_seconds)
            bucket["avg_rest_count"] += 1
        if session.duration_seconds is not None:
            bucket["duration_sum"] += int(session.duration_seconds)
            bucket["duration_count"] += 1

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "week_start",
        "workouts",
        "total_volume",
        "total_tonnage",
        "avg_completion_rate",
        "avg_rpe",
        "avg_rest_seconds",
        "avg_duration_seconds",
    ])

    for key in sorted(weekly.keys()):
        bucket = weekly[key]
        completion_rate = bucket["completion_rate_sum"] / bucket["workouts"] if bucket["workouts"] else 0
        avg_rpe = bucket["avg_rpe_sum"] / bucket["avg_rpe_count"] if bucket["avg_rpe_count"] else ""
        avg_rest = bucket["avg_rest_sum"] / bucket["avg_rest_count"] if bucket["avg_rest_count"] else ""
        avg_duration = bucket["duration_sum"] / bucket["duration_count"] if bucket["duration_count"] else ""
        writer.writerow([
            bucket["week_start"].strftime("%Y-%m-%d"),
            bucket["workouts"],
            round(bucket["total_volume"], 2),
            round(bucket["total_tonnage"], 2),
            round(completion_rate, 3),
            round(avg_rpe, 2) if avg_rpe != "" else "",
            round(avg_rest, 2) if avg_rest != "" else "",
            round(avg_duration, 2) if avg_duration != "" else "",
        ])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=weekly_stats_{period}.csv"
    return response

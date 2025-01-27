# stats_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta
import pytz
import logging

from init_db import db
from models import User, Workout

stats_bp = Blueprint('stats_bp', __name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@stats_bp.route('/historical_data/<muscle_group>', methods=['GET'])
def historical_data(muscle_group):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    current_datetime = datetime.now(pytz.UTC)
    current_date = current_datetime.date()
    historical_start_date = current_date - timedelta(days=180)

    # Define the start and end datetime for the historical range
    start_datetime = datetime.combine(historical_start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    end_datetime = datetime.combine(current_date, datetime.max.time()).replace(tzinfo=pytz.UTC)

    historical_workouts = Workout.query.filter(
        Workout.user_id == user_id,
        Workout.is_completed == True,
        Workout.workout_date >= start_datetime,
        Workout.workout_date <= end_datetime
    ).all()

    historical_data = []
    for workout in historical_workouts:
        for wm in workout.workout_movements:
            for mg in wm.muscle_groups:
                if mg.name == muscle_group:
                    volume = wm.sets * wm.reps_per_set * wm.weight * (mg.impact / 100)
                    historical_data.append({
                        'date': workout.workout_date.strftime('%Y-%m-%d'),
                        'volume': volume
                    })

    historical_data.sort(key=lambda x: x['date'])
    return jsonify(historical_data)


@stats_bp.route('/stats', methods=['GET'])
def stats():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth_bp.login'))

    time_filter = request.args.get('time_filter', 'all')
    current_datetime = datetime.now(pytz.UTC)
    current_date = current_datetime.date()

    if time_filter == 'weekly':
        period_length = 7
    elif time_filter == 'monthly':
        period_length = 30
    elif time_filter == 'all':
        period_length = 180
    else:
        period_length = 30

    current_start_date = current_date - timedelta(days=period_length)
    previous_start_date = current_start_date - timedelta(days=period_length)

    # Define datetime ranges
    current_start_datetime = datetime.combine(current_start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    current_end_datetime = datetime.combine(current_date, datetime.max.time()).replace(tzinfo=pytz.UTC)
    previous_start_datetime = datetime.combine(previous_start_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    previous_end_datetime = datetime.combine(current_start_date, datetime.max.time()).replace(tzinfo=pytz.UTC)

    logger.info(f"Fetching current workouts from {current_start_datetime} to {current_end_datetime}")
    logger.info(f"Fetching previous workouts from {previous_start_datetime} to {previous_end_datetime}")

    # Fetch current workouts
    current_workouts = (
        Workout.query
        .filter(
            Workout.user_id == user_id,
            Workout.is_completed == True,
            Workout.workout_date >= current_start_datetime,
            Workout.workout_date <= current_end_datetime
        )
        .all()
    )

    logger.info(f"Current Workouts Count: {len(current_workouts)}")
    for w in current_workouts:
        logger.info(f"Workout ID: {w.workout_id}, Workout Date: {w.workout_date}")

    # Fetch previous workouts
    previous_workouts = (
        Workout.query
        .filter(
            Workout.user_id == user_id,
            Workout.is_completed == True,
            Workout.workout_date >= previous_start_datetime,
            Workout.workout_date <= previous_end_datetime
        )
        .all()
    )

    logger.info(f"Previous Workouts Count: {len(previous_workouts)}")
    for w in previous_workouts:
        logger.info(f"Workout ID: {w.workout_id}, Workout Date: {w.workout_date}")

    def calculate_workloads(workouts):
        workloads = {}
        for w in workouts:
            for wm in w.workout_movements:
                mg_impacts = wm.calculate_muscle_group_impact()
                for mg_name, impact_value in mg_impacts.items():
                    workloads[mg_name] = workloads.get(mg_name, 0) + impact_value
        return workloads

    current_values = calculate_workloads(current_workouts)
    previous_values = calculate_workloads(previous_workouts)

    muscle_group_changes = []
    for mg_name, current_value in current_values.items():
        prev_val = previous_values.get(mg_name, 0)
        if prev_val > 0:
            change = ((current_value - prev_val) / prev_val) * 100.0
        else:
            change = 100.0 if current_value > 0 else 0.0

        muscle_group_changes.append(
            (mg_name, round(current_value, 2), round(change, 2))
        )

    top_changes = sorted(
        muscle_group_changes,
        key=lambda x: abs(x[2]),
        reverse=True
    )[:5]

    progress_data = {
        mg_name: {
            'current_value': val,
            'change_percentage': pct
        }
        for mg_name, val, pct in top_changes
    }

    logger.info(f"Progress data (top 5 muscle groups): {progress_data}")
    logger.info(f"Muscle group changes: {muscle_group_changes}")

    return render_template(
        'stats.html',
        workouts=current_workouts,
        progress_data=progress_data,
        time_filter=time_filter
    )

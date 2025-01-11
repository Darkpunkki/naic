# stats_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta

from init_db import db
from models import User, Workout

stats_bp = Blueprint('stats_bp', __name__)

@stats_bp.route('/historical_data/<muscle_group>', methods=['GET'])
def historical_data(muscle_group):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    current_date = datetime.now().date()
    historical_start_date = current_date - timedelta(days=180)

    historical_workouts = Workout.query.filter(
        Workout.user_id == user_id,
        Workout.completion_date != None,
        Workout.completion_date >= historical_start_date,
        Workout.completion_date < current_date
    ).all()

    historical_data = []
    for workout in historical_workouts:
        for wm in workout.workout_movements:
            for mg in wm.movement.muscle_groups:
                if mg.muscle_group.name == muscle_group:
                    volume = wm.sets * wm.reps_per_set * wm.weight * (mg.impact / 100)
                    historical_data.append({
                        'date': workout.completion_date.strftime('%Y-%m-%d'),
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
    current_date = datetime.now().date()

    if time_filter == 'weekly':
        period_length = 7
    elif time_filter == 'monthly':
        period_length = 30
    else:
        period_length = 30

    current_start_date = current_date - timedelta(days=period_length)
    previous_start_date = current_start_date - timedelta(days=period_length)

    current_workouts = (
        Workout.query
        .filter(
            Workout.user_id == user_id,
            Workout.is_completed == True,
            Workout.workout_date >= current_start_date,
            Workout.workout_date <= current_date
        )
        .all()
    )

    previous_workouts = (
        Workout.query
        .filter(
            Workout.user_id == user_id,
            Workout.is_completed == True,
            Workout.workout_date >= previous_start_date,
            Workout.workout_date < current_start_date
        )
        .all()
    )

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

    print(f"Progress data (top 5 muscle groups): {progress_data}")
    print(f"Muscle group changes: {muscle_group_changes}")

    return render_template(
        'stats.html',
        workouts=current_workouts,
        progress_data=progress_data,
        time_filter=time_filter
    )

"""Workout duplication routes (single workout and weekly group)."""
from datetime import datetime

from flask import request, session, jsonify

from app.services.workout_service import WorkoutService

from app.routes.workouts.blueprint import workouts_bp


@workouts_bp.route('/duplicate_workout/<int:workout_id>', methods=['POST'])
def duplicate_workout(workout_id):
    """Duplicate a single workout to a new date."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    target_date_str = data.get('target_date')

    if not target_date_str:
        return jsonify({'error': 'Target date is required'}), 400

    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        new_workout = WorkoutService.duplicate_workout(
            workout_id,
            session['user_id'],
            target_date
        )
        return jsonify({
            'success': True,
            'workout_id': new_workout.workout_id,
            'message': 'Workout duplicated successfully'
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to duplicate workout'}), 500


@workouts_bp.route('/duplicate_workout_group/<group_id>', methods=['POST'])
def duplicate_workout_group(group_id):
    """Duplicate all workouts in a weekly group to new dates."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    start_date_str = data.get('start_date')

    if not start_date_str:
        return jsonify({'error': 'Start date is required'}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        new_workouts = WorkoutService.duplicate_workout_group(
            group_id,
            session['user_id'],
            start_date
        )
        return jsonify({
            'success': True,
            'workout_count': len(new_workouts),
            'workout_ids': [w.workout_id for w in new_workouts],
            'message': f'Successfully duplicated {len(new_workouts)} workouts'
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to duplicate workout group'}), 500

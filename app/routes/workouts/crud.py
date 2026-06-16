"""Core workout CRUD: view, create, update, complete, delete, and JSON export."""
from datetime import datetime, date

from flask import render_template, request, redirect, url_for, session, flash, jsonify

from app.models import Movement, Workout, User, db
from app.services.workout_service import WorkoutService

from app.routes.workouts.blueprint import workouts_bp


@workouts_bp.route('/new_workout', methods=['POST'])
def new_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    data = request.get_json()
    if not data or 'workoutDate' not in data:
        return jsonify({'error': 'Invalid data submitted'}), 400

    try:
        workout_date = datetime.strptime(data['workoutDate'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    workout = WorkoutService.create_blank_workout(session['user_id'], workout_date)
    return jsonify({'workout_id': workout.workout_id}), 200


@workouts_bp.route('/workout/<int:workout_id>', methods=['GET'])
def view_workout(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    workout = Workout.query.get_or_404(workout_id)

    # Authorization check: ensure user owns this workout
    if workout.user_id != session['user_id']:
        flash("You don't have permission to view this workout.", "error")
        return redirect(url_for('main_bp.index')), 403

    user = User.query.get(session['user_id'])

    date_str = workout.workout_date.strftime("%Y-%m-%d") if workout.workout_date else ""
    date_str_today = date.today().strftime("%Y-%m-%d")

    # Get all movements for dropdown
    all_movements = sorted(Movement.query.all(), key=lambda m: m.movement_name)
    movements_with_muscle_groups = [
        {
            'movement_id': m.movement_id,
            'movement_name': m.movement_name,
            'muscle_groups': [
                {
                    'muscle_group_name': mmg.muscle_group.muscle_group_name,
                    'target_percentage': mmg.target_percentage
                }
                for mmg in m.muscle_groups
            ]
        }
        for m in all_movements
    ]

    # Calculate muscle group impacts if completed
    muscle_group_impacts = None
    if workout.is_completed:
        aggregate_impacts = {}
        for wm in workout.workout_movements:
            for mg_name, impact_value in wm.calculate_muscle_group_impact().items():
                aggregate_impacts[mg_name] = aggregate_impacts.get(mg_name, 0) + impact_value
        muscle_group_impacts = sorted(aggregate_impacts.items(), key=lambda x: x[1], reverse=True)

    return render_template(
        'workout_details.html',
        confirm_mode=False,
        workout=workout,
        all_movements=movements_with_muscle_groups,
        from_select_workout=request.args.get('from_select_workout') == 'True',
        muscle_group_impacts=muscle_group_impacts,
        user=user,
        date_str=date_str,
        date_str_today=date_str_today
    )


@workouts_bp.route('/update_workout_date/<int:workout_id>', methods=['POST'])
def update_workout_date(workout_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    # Authorization check: ensure user owns this workout
    workout = Workout.query.get_or_404(workout_id)
    if workout.user_id != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403

    is_json_request = request.is_json
    new_date_str = request.get_json().get('new_date') if is_json_request else request.form.get('new_date')

    if not new_date_str:
        if is_json_request:
            return jsonify({'error': 'Invalid date submitted'}), 400
        flash('Invalid date submitted.', 'error')
        return redirect(url_for('workouts.view_workout', workout_id=workout_id))

    try:
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        WorkoutService.update_workout_date(workout_id, new_date)

        if is_json_request:
            return jsonify({'success': True, 'message': 'Workout date updated', 'new_date': new_date_str})
        flash('Workout date updated successfully.', 'success')
    except ValueError:
        if is_json_request:
            return jsonify({'error': 'Invalid date format'}), 400
        flash('Invalid date format.', 'error')

    return redirect(url_for('workouts.view_workout', workout_id=workout_id))


@workouts_bp.route('/update_workout_name/<int:workout_id>', methods=['POST'])
def update_workout_name(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # Authorization check: ensure user owns this workout
    workout = Workout.query.get_or_404(workout_id)
    if workout.user_id != session['user_id']:
        flash("You don't have permission to modify this workout.", "error")
        return redirect(url_for('main_bp.index')), 403

    new_name = request.form.get('workoutName')
    if not new_name:
        return "Workout name cannot be empty.", 400

    workout = WorkoutService.update_workout_name(workout_id, new_name)
    return redirect(url_for('workouts.view_workout', workout_id=workout.workout_id))


@workouts_bp.route('/update_workout/<int:workout_id>', methods=['POST'])
def update_workout(workout_id):
    WorkoutService.update_workout_data(workout_id, request.form)
    flash("Workout updated successfully!", "success")
    return redirect(url_for('workouts.view_workout', workout_id=workout_id))


@workouts_bp.route('/complete_workout', methods=['POST'])
def complete_workout():
    workout_id = request.form.get('workout_id', type=int)

    completion_date_str = request.form.get('completion_date')
    completion_date = None
    if completion_date_str:
        try:
            completion_date = datetime.strptime(completion_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "error")
            return redirect(url_for('workouts.view_workout', workout_id=workout_id))

    WorkoutService.complete_workout(workout_id, request.form, completion_date)
    flash("Workout marked as completed!", "success")
    return redirect(url_for('main_bp.index'))


@workouts_bp.route('/delete_workout/<int:workout_id>', methods=['POST'])
def delete_workout(workout_id):
    WorkoutService.delete_workout(workout_id)
    flash("Workout has been removed.", "success")
    return redirect(url_for('main_bp.index'))


@workouts_bp.route('/delete_if_empty/<int:workout_id>', methods=['POST'])
def delete_if_empty(workout_id):
    """Delete a workout only if it has no movements. Used for cleanup when navigating away."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    workout = Workout.query.get(workout_id)
    if not workout:
        return jsonify({'deleted': False, 'reason': 'Workout not found'}), 404

    if workout.user_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    if len(workout.workout_movements) == 0:
        WorkoutService.delete_workout(workout_id)
        return jsonify({'deleted': True, 'message': 'Empty workout deleted'})

    return jsonify({'deleted': False, 'reason': 'Workout has movements'})


@workouts_bp.route('/user_data', methods=['GET'])
def user_data():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get_or_404(session['user_id'])
    data = []

    for workout in user.workouts:
        movements = [
            {
                "name": wm.movement.movement_name,
                "sets": len(wm.sets),
                "reps_per_set": wm.sets[0].reps[0].rep_count if wm.sets and wm.sets[0].reps else 0,
                "weight": float(wm.sets[0].weights[0].weight_value) if wm.sets and wm.sets[0].weights else 0,
                "done": wm.done if hasattr(wm, 'done') else False,
            }
            for wm in workout.workout_movements
        ]
        data.append({
            "workout_id": workout.workout_id,
            "name": workout.workout_name,
            "date": workout.workout_date.strftime('%Y-%m-%d') if workout.workout_date else None,
            "is_completed": workout.is_completed,
            "movements": movements,
        })

    return jsonify(data)


@workouts_bp.route('/update_status', methods=['POST'])
def update_status():
    workout_id = request.form.get('workout_id', type=int)
    new_status = request.form.get('status')

    workout = Workout.query.get_or_404(workout_id)
    workout.status = new_status
    db.session.commit()

    return redirect(url_for('workouts.view_workout', workout_id=workout.id))


@workouts_bp.route('/update_workout_movements', methods=['POST'])
def update_workout_movements():
    workout_id = request.form.get('workout_id', type=int)
    workout = Workout.query.get_or_404(workout_id)

    for wm in workout.workout_movements:
        wm.sets = request.form.get(f"sets_{wm.id}", type=int, default=wm.sets)
        wm.reps_per_set = request.form.get(f"reps_{wm.id}", type=int, default=wm.reps_per_set)
        wm.weight = request.form.get(f"weight_{wm.id}", type=float, default=wm.weight)
        wm.done = f"done_{wm.id}" in request.form

    db.session.commit()
    flash("Workout movements updated successfully!", "success")
    return redirect(url_for('workouts.view_workout', workout_id=workout_id))

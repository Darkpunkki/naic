"""
Workout Routes - Thin endpoint definitions delegating to services.
"""
from datetime import datetime, date

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from app.models import (
    Movement,
    Workout,
    WorkoutMovement,
    User,
    db,
)
from app.services.workout_service import WorkoutService
from app.services.movement_service import MovementService
from app.services.ai_generation_service import AIGenerationService


workouts_bp = Blueprint("workouts", __name__)


# -----------------------------
# Dashboard / Navigation
# -----------------------------

@workouts_bp.route('/start_workout', methods=['GET'])
def start_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    workouts = Workout.query.filter_by(user_id=session['user_id']).all()
    return render_template('start_workout.html', workouts=workouts)


# -----------------------------
# Workout CRUD
# -----------------------------

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
    workout = Workout.query.get_or_404(workout_id)
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


@workouts_bp.route('/active_workout/<int:workout_id>', methods=['GET'])
def active_workout(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    workout = Workout.query.get_or_404(workout_id)

    if workout.user_id != session['user_id']:
        flash("Unauthorized access to the workout.", "error")
        return redirect(url_for('main_bp.index'))

    # Update workout date to current date when starting
    today = date.today()
    if workout.workout_date != today:
        WorkoutService.update_workout_date(workout_id, today)

    return render_template('active_workout.html', workout=workout)


@workouts_bp.route('/update_workout_date/<int:workout_id>', methods=['POST'])
def update_workout_date(workout_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

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


@workouts_bp.route('/all_workouts')
def all_workouts():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    filter_value = request.args.get('filter', 'all')
    filter_completed = None
    if filter_value == 'completed':
        filter_completed = True
    elif filter_value == 'incomplete':
        filter_completed = False

    workouts = WorkoutService.get_user_workouts(session['user_id'], filter_completed)
    return render_template('all_workouts.html', workouts=workouts)


@workouts_bp.route('/select_workout', methods=['GET'])
def select_workout():
    workout_id = request.args.get('workout_id')
    if not workout_id:
        return "No workout selected!"

    workout = Workout.query.get_or_404(workout_id)
    if workout.status == 'planned':
        workout.status = 'started'
        db.session.commit()

    return redirect(url_for('workouts.view_workout', workout_id=workout.id))


@workouts_bp.route('/select_workout/<int:workout_id>', methods=['GET'])
def select_workout_by_id(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    if workout.status == 'planned':
        workout.status = 'started'
        db.session.commit()

    return redirect(url_for('workouts.view_workout', workout_id=workout.id, from_select_workout=True))


# -----------------------------
# Movement Management
# -----------------------------

@workouts_bp.route('/add_movement', methods=['POST'])
def add_movement():
    workout_id = request.form.get('workout_id', type=int)
    movement_option = request.form.get('movement_option', 'existing')
    set_count = request.form.get('sets', type=int, default=1)
    reps_per_set = request.form.get('reps_per_set', type=int, default=10)
    weight_value = request.form.get('weight', type=float, default=0.0)

    if movement_option == 'existing':
        movement_id = request.form.get('movement_id', type=int)
        if not movement_id:
            flash("No existing movement selected.", "error")
            return redirect(url_for('workouts.view_workout', workout_id=workout_id))

        movement = Movement.query.get_or_404(movement_id)
        MovementService.add_movement_to_workout(
            workout_id,
            movement.movement_name,
            set_count,
            reps_per_set,
            weight_value,
            is_bodyweight=False
        )
    else:
        # New movement - will fetch muscle groups via AI
        new_movement_name = request.form.get('new_movement_name', '').strip()
        if not new_movement_name:
            flash("No new movement name provided.", "error")
            return redirect(url_for('workouts.view_workout', workout_id=workout_id))

        MovementService.add_movement_to_workout(
            workout_id,
            new_movement_name,
            set_count,
            reps_per_set,
            weight_value,
            is_bodyweight=False
        )

    flash("Movement added to workout!", "success")
    return redirect(url_for('workouts.view_workout', workout_id=workout_id))


@workouts_bp.route('/remove_movement/<int:workout_movement_id>', methods=['POST'])
def remove_movement(workout_movement_id):
    workout_id = MovementService.remove_movement_from_workout(workout_movement_id)
    flash("Movement removed from workout.", "info")
    return redirect(url_for('workouts.view_workout', workout_id=workout_id))


@workouts_bp.route('/generate_movements/<int:workout_id>', methods=['POST'])
def generate_movements(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])

    sex = user.sex or request.form.get('sex', 'Unknown')
    weight = user.bodyweight or request.form.get('weight', '70')
    gymexp = user.gym_experience or request.form.get('gymexp', 'beginner')
    target = request.form.get('target', 'general fitness')
    goal = request.form.get('goal') or user.workout_goal or 'general_fitness'
    restrictions = request.form.get('restrictions', '')

    try:
        workout_plan = AIGenerationService.generate_single_workout(
            sex, weight, gymexp, target, goal, restrictions
        )
        WorkoutService.generate_and_add_movements(workout_id, workout_plan)
        flash("Movements generated and added to your workout!", "success")
    except Exception as e:
        flash(f"Error generating movements: {str(e)}", "error")

    return redirect(url_for('workouts.view_workout', workout_id=workout_id))


@workouts_bp.route('/get_instructions', methods=['GET'])
def get_instructions():
    movement_name = request.args.get('movement_name', '')
    if not movement_name:
        return jsonify({'error': 'No movement name provided'}), 400

    try:
        instructions = AIGenerationService.get_movement_instructions(movement_name)
        return jsonify({'instructions': instructions}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch instructions'}), 500


# -----------------------------
# AI Single Workout Generation
# -----------------------------

@workouts_bp.route('/generate_workout', methods=['GET', 'POST'])
def generate_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        sex = user.sex or request.form.get('sex', 'Unknown')
        bodyweight = user.bodyweight or request.form.get('weight', 70)
        gymexp = user.gym_experience or request.form.get('gymexp', 'beginner')
        target = request.form.get('target') or session.get('pending_target', 'General Fitness')
        goal = request.form.get('goal') or user.workout_goal or 'general_fitness'
        restrictions = request.form.get('restrictions', '')

        try:
            workout_json = AIGenerationService.generate_single_workout(
                sex, bodyweight, gymexp, target, goal, restrictions
            )
            session['pending_workout_plan'] = workout_json
            session['pending_target'] = workout_json.get("workout_name", target)
            session['pending_workout_goal'] = goal  # Preserve goal for confirmation
            return redirect(url_for('workouts.confirm_workout'))
        except Exception as e:
            flash(f"Error generating workout plan: {str(e)}", 'error')
            return redirect(url_for('workouts.generate_workout'))

    return render_template('generate_workout.html', user=user)


@workouts_bp.route('/confirm_workout', methods=['GET', 'POST'])
def confirm_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    workout_json = session.get('pending_workout_plan')
    if not workout_json:
        flash("No workout plan found to confirm!", 'error')
        return redirect(url_for('workouts.generate_workout'))

    if request.method == 'POST':
        workout = WorkoutService.create_workout_from_plan(
            session['user_id'],
            workout_json,
            datetime.now()
        )
        session.pop('pending_workout_plan', None)
        session.pop('pending_workout_goal', None)  # Clean up goal from session
        flash("Workout successfully created!", 'success')
        return redirect(url_for('workouts.view_workout', workout_id=workout.workout_id))

    # Get all movements for the add movement dropdown
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

    workout_goal = session.get('pending_workout_goal', 'general_fitness')
    return render_template(
        'workout_details.html',
        confirm_mode=True,
        pending_workout=workout_json,
        workout=None,
        workout_goal=workout_goal,
        all_movements=movements_with_muscle_groups,
        date_str_today=date.today().strftime("%Y-%m-%d")
    )


# -----------------------------
# Pending Workout Modifications
# -----------------------------

@workouts_bp.route('/pending_workout/update_movement', methods=['POST'])
def update_pending_movement():
    """Update sets/reps/weight for a movement in the pending workout plan."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    workout_json = session.get('pending_workout_plan')
    if not workout_json:
        return jsonify({'error': 'No pending workout found'}), 404

    data = request.get_json()
    index = data.get('index')
    sets = data.get('sets')
    reps = data.get('reps')
    weight = data.get('weight')

    if index is None or index < 0 or index >= len(workout_json.get('movements', [])):
        return jsonify({'error': 'Invalid movement index'}), 400

    # Update the movement
    if sets is not None:
        workout_json['movements'][index]['sets'] = int(sets)
    if reps is not None:
        workout_json['movements'][index]['reps'] = int(reps)
    if weight is not None:
        workout_json['movements'][index]['weight'] = float(weight)

    session['pending_workout_plan'] = workout_json
    session.modified = True

    return jsonify({'success': True, 'movement': workout_json['movements'][index]})


@workouts_bp.route('/pending_workout/remove_movement/<int:index>', methods=['POST'])
def remove_pending_movement(index):
    """Remove a movement from the pending workout plan."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    workout_json = session.get('pending_workout_plan')
    if not workout_json:
        return jsonify({'error': 'No pending workout found'}), 404

    movements = workout_json.get('movements', [])
    if index < 0 or index >= len(movements):
        return jsonify({'error': 'Invalid movement index'}), 400

    # Remove the movement
    removed = movements.pop(index)
    session['pending_workout_plan'] = workout_json
    session.modified = True

    return jsonify({'success': True, 'removed': removed['name']})


@workouts_bp.route('/pending_workout/add_movement', methods=['POST'])
def add_pending_movement():
    """Add an existing movement to the pending workout plan."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    workout_json = session.get('pending_workout_plan')
    if not workout_json:
        return jsonify({'error': 'No pending workout found'}), 404

    data = request.get_json()
    movement_id = data.get('movement_id')
    sets = data.get('sets', 3)
    reps = data.get('reps', 10)
    weight = data.get('weight', 0)

    if not movement_id:
        return jsonify({'error': 'No movement selected'}), 400

    # Get the movement from database
    movement = Movement.query.get(movement_id)
    if not movement:
        return jsonify({'error': 'Movement not found'}), 404

    # Build movement dict matching the pending plan structure
    muscle_groups = [
        {
            'name': mmg.muscle_group.muscle_group_name,
            'impact': mmg.target_percentage
        }
        for mmg in movement.muscle_groups
    ]

    new_movement = {
        'name': movement.movement_name,
        'sets': int(sets),
        'reps': int(reps),
        'weight': float(weight),
        'is_bodyweight': weight == 0,
        'muscle_groups': muscle_groups
    }

    workout_json['movements'].append(new_movement)
    session['pending_workout_plan'] = workout_json
    session.modified = True

    return jsonify({'success': True, 'movement': new_movement})


# -----------------------------
# Pending Weekly Workout Modifications
# -----------------------------

@workouts_bp.route('/pending_weekly/update_movement', methods=['POST'])
def update_pending_weekly_movement():
    """Update sets/reps/weight for a movement in the pending weekly plan."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    weekly_plan = session.get('pending_weekly_plan')
    if not weekly_plan:
        return jsonify({'error': 'No pending weekly plan found'}), 404

    data = request.get_json()
    day_index = data.get('day_index')
    movement_index = data.get('movement_index')
    sets = data.get('sets')
    reps = data.get('reps')
    weight = data.get('weight')

    plan_list = weekly_plan.get('weekly_plan', [])

    if day_index is None or day_index < 0 or day_index >= len(plan_list):
        return jsonify({'error': 'Invalid day index'}), 400

    movements = plan_list[day_index].get('movements', [])

    if movement_index is None or movement_index < 0 or movement_index >= len(movements):
        return jsonify({'error': 'Invalid movement index'}), 400

    # Update the movement
    if sets is not None:
        weekly_plan['weekly_plan'][day_index]['movements'][movement_index]['sets'] = int(sets)
    if reps is not None:
        weekly_plan['weekly_plan'][day_index]['movements'][movement_index]['reps'] = int(reps)
    if weight is not None:
        weekly_plan['weekly_plan'][day_index]['movements'][movement_index]['weight'] = float(weight)

    session['pending_weekly_plan'] = weekly_plan
    session.modified = True

    return jsonify({
        'success': True,
        'movement': weekly_plan['weekly_plan'][day_index]['movements'][movement_index]
    })


@workouts_bp.route('/pending_weekly/remove_movement', methods=['POST'])
def remove_pending_weekly_movement():
    """Remove a movement from the pending weekly plan."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    weekly_plan = session.get('pending_weekly_plan')
    if not weekly_plan:
        return jsonify({'error': 'No pending weekly plan found'}), 404

    data = request.get_json()
    day_index = data.get('day_index')
    movement_index = data.get('movement_index')

    plan_list = weekly_plan.get('weekly_plan', [])

    if day_index is None or day_index < 0 or day_index >= len(plan_list):
        return jsonify({'error': 'Invalid day index'}), 400

    movements = plan_list[day_index].get('movements', [])

    if movement_index is None or movement_index < 0 or movement_index >= len(movements):
        return jsonify({'error': 'Invalid movement index'}), 400

    # Remove the movement
    removed = movements.pop(movement_index)
    session['pending_weekly_plan'] = weekly_plan
    session.modified = True

    return jsonify({'success': True, 'removed': removed['name']})


@workouts_bp.route('/pending_weekly/add_movement', methods=['POST'])
def add_pending_weekly_movement():
    """Add an existing movement to a day in the pending weekly plan."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    weekly_plan = session.get('pending_weekly_plan')
    if not weekly_plan:
        return jsonify({'error': 'No pending weekly plan found'}), 404

    data = request.get_json()
    day_index = data.get('day_index')
    movement_id = data.get('movement_id')
    sets = data.get('sets', 3)
    reps = data.get('reps', 10)
    weight = data.get('weight', 0)

    plan_list = weekly_plan.get('weekly_plan', [])

    if day_index is None or day_index < 0 or day_index >= len(plan_list):
        return jsonify({'error': 'Invalid day index'}), 400

    if not movement_id:
        return jsonify({'error': 'No movement selected'}), 400

    # Get the movement from database
    movement = Movement.query.get(movement_id)
    if not movement:
        return jsonify({'error': 'Movement not found'}), 404

    # Build movement dict matching the pending plan structure
    muscle_groups = [
        {
            'name': mmg.muscle_group.muscle_group_name,
            'impact': mmg.target_percentage
        }
        for mmg in movement.muscle_groups
    ]

    new_movement = {
        'name': movement.movement_name,
        'sets': int(sets),
        'reps': int(reps),
        'weight': float(weight),
        'is_bodyweight': weight == 0,
        'muscle_groups': muscle_groups
    }

    weekly_plan['weekly_plan'][day_index]['movements'].append(new_movement)
    session['pending_weekly_plan'] = weekly_plan
    session.modified = True

    return jsonify({'success': True, 'movement': new_movement})


# -----------------------------
# AI Weekly Workout Generation
# -----------------------------

@workouts_bp.route('/generate_weekly_workout', methods=['GET', 'POST'])
def generate_weekly_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        sex = user.sex or request.form.get('sex', 'Unknown')
        weight = user.bodyweight or request.form.get('weight', 70)
        gymexp = user.gym_experience or request.form.get('gymexp', 'beginner')
        target = request.form.get('target', 'General Fitness')
        gym_days = int(request.form.get('gym_days', 3))
        session_duration = int(request.form.get('session_duration', 60))
        goal = request.form.get('goal') or user.workout_goal or 'general_fitness'
        restrictions = request.form.get('restrictions', '')

        try:
            weekly_plan = AIGenerationService.generate_weekly_workout(
                sex, weight, gymexp, target, gym_days, session_duration, goal, restrictions
            )
            session['pending_weekly_plan'] = weekly_plan
            return redirect(url_for('workouts.confirm_weekly_workout'))
        except Exception as e:
            flash(f"Error generating weekly workout plan: {str(e)}", 'error')
            return redirect(url_for('workouts.generate_weekly_workout'))

    return render_template('generate_weekly_workout.html', user=user)


@workouts_bp.route('/confirm_weekly_workout', methods=['GET', 'POST'])
def confirm_weekly_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    weekly_plan = session.get('pending_weekly_plan')
    if not weekly_plan:
        flash("No weekly workout plan found to confirm!", 'error')
        return redirect(url_for('workouts.generate_weekly_workout'))

    if request.method == 'POST':
        # Parse selected dates if provided
        selected_dates_json = request.form.get('selected_dates')
        specific_dates = None

        if selected_dates_json:
            import json
            try:
                date_strings = json.loads(selected_dates_json)
                specific_dates = [
                    datetime.strptime(d, '%Y-%m-%d').date()
                    for d in date_strings
                ]
            except (json.JSONDecodeError, ValueError):
                flash("Invalid date selection format", 'error')
                return redirect(url_for('workouts.confirm_weekly_workout'))

        WorkoutService.create_weekly_workouts_from_plan(
            session['user_id'],
            weekly_plan,
            datetime.today().date(),
            specific_dates=specific_dates
        )
        session.pop('pending_weekly_plan', None)
        flash("Weekly workout plan successfully created!", 'success')
        return redirect(url_for('workouts.all_workouts'))

    # Get all movements for the add movement dropdown
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

    return render_template(
        'confirm_weekly_workout.html',
        weekly_plan=weekly_plan,
        all_movements=movements_with_muscle_groups,
        date_str_today=date.today().strftime("%Y-%m-%d")
    )


# -----------------------------
# API Endpoints
# -----------------------------

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

"""Weekly-plan AI generation, confirmation, and pending-weekly editing."""
from datetime import datetime, date

from flask import render_template, request, redirect, url_for, session, flash, jsonify

from app.models import Movement, User
from app.services.workout_service import WorkoutService
from app.services.ai_generation_service import AIGenerationService
from app.guards import (
    require_auth,
    rate_limit_llm,
    WeeklyWorkoutGenerationInput,
    MovementInput,
    PendingWorkoutUpdateInput,
    ValidationError,
    validate_request,
    ContentFilterError,
)

from app.routes.workouts.blueprint import workouts_bp


@workouts_bp.route('/cancel_pending_weekly', methods=['POST'])
@require_auth
def cancel_pending_weekly():
    """Clear pending weekly plan from session."""
    session.pop('pending_weekly_plan', None)
    return jsonify({'success': True})


# -----------------------------
# AI Weekly Workout Generation
# -----------------------------

@workouts_bp.route('/generate_weekly_workout', methods=['GET', 'POST'])
@require_auth
@rate_limit_llm
def generate_weekly_workout():
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

        # Validate input
        try:
            validated = validate_request(WeeklyWorkoutGenerationInput, {
                'target': target,
                'restrictions': restrictions,
                'goal': goal,
                'gym_days': gym_days,
                'session_duration': session_duration
            })
            target = validated['target']
            restrictions = validated['restrictions']
            goal = validated['goal']
            gym_days = validated['gym_days']
            session_duration = validated['session_duration']
        except ValidationError as e:
            flash(f"Invalid input: {e.message}", 'error')
            return redirect(url_for('workouts.generate_weekly_workout'))

        try:
            weekly_plan = AIGenerationService.generate_weekly_workout(
                sex, weight, gymexp, target, gym_days, session_duration, goal, restrictions,
                user_id=session['user_id']
            )
            session['pending_weekly_plan'] = weekly_plan
            return redirect(url_for('workouts.confirm_weekly_workout'))
        except ContentFilterError as e:
            flash(e.message, 'error')
            return redirect(url_for('workouts.generate_weekly_workout'))
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
# Pending Weekly Workout Modifications
# -----------------------------

@workouts_bp.route('/pending_weekly/update_movement', methods=['POST'])
@require_auth
def update_pending_weekly_movement():
    """Update sets/reps/weight for a movement in the pending weekly plan."""
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

    # Validate numeric inputs
    try:
        validated = validate_request(PendingWorkoutUpdateInput, {
            'index': movement_index,
            'sets': sets,
            'reps': reps,
            'weight': weight
        })
        sets = validated.get('sets')
        reps = validated.get('reps')
        weight = validated.get('weight')
    except ValidationError as e:
        return jsonify({'error': e.message}), 400

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
@require_auth
def remove_pending_weekly_movement():
    """Remove a movement from the pending weekly plan."""
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
@require_auth
def add_pending_weekly_movement():
    """Add an existing movement to a day in the pending weekly plan."""
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

    # Validate numeric inputs
    try:
        validated = validate_request(MovementInput, {
            'movement_name': 'placeholder',
            'sets': sets,
            'reps': reps,
            'weight': weight
        })
        sets = validated['sets']
        reps = validated['reps']
        weight = validated['weight']
    except ValidationError as e:
        return jsonify({'error': e.message}), 400

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

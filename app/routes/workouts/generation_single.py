"""Single-workout AI generation, confirmation, and pending-plan editing."""
import logging
from datetime import datetime, date

from flask import render_template, request, redirect, url_for, session, flash, jsonify

from app.models import Movement, User
from app.services.workout_service import WorkoutService
from app.services.movement_service import MovementService
from app.services.ai_generation_service import AIGenerationService
from app.guards import (
    require_auth,
    rate_limit_llm,
    WorkoutGenerationInput,
    MovementInput,
    PendingWorkoutUpdateInput,
    ValidationError,
    validate_request,
    ContentFilterError,
)

from app.routes.workouts.blueprint import workouts_bp

logger = logging.getLogger(__name__)


# -----------------------------
# AI Single Workout Generation
# -----------------------------

@workouts_bp.route('/generate_workout', methods=['GET', 'POST'])
@require_auth
@rate_limit_llm
def generate_workout():
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        sex = user.sex or request.form.get('sex', 'Unknown')
        bodyweight = user.bodyweight or request.form.get('weight', 70)
        gymexp = user.gym_experience or request.form.get('gymexp', 'beginner')
        target = request.form.get('target') or session.get('pending_target', 'General Fitness')
        goal = request.form.get('goal') or user.workout_goal or 'general_fitness'
        restrictions = request.form.get('restrictions', '')

        # Validate input
        try:
            validated = validate_request(WorkoutGenerationInput, {
                'target': target,
                'restrictions': restrictions,
                'goal': goal
            })
            target = validated['target']
            restrictions = validated['restrictions']
            goal = validated['goal']
        except ValidationError as e:
            flash(f"Invalid input: {e.message}", 'error')
            return redirect(url_for('workouts.generate_workout'))

        try:
            workout_json = AIGenerationService.generate_single_workout(
                sex, bodyweight, gymexp, target, goal, restrictions,
                user_id=session['user_id']
            )
            session['pending_workout_plan'] = workout_json
            session['pending_target'] = workout_json.get("workout_name", target)
            session['pending_workout_goal'] = goal  # Preserve goal for confirmation
            return redirect(url_for('workouts.confirm_workout'))
        except ContentFilterError as e:
            flash(e.message, 'error')
            return redirect(url_for('workouts.generate_workout'))
        except Exception as e:
            flash(f"Error generating workout plan: {str(e)}", 'error')
            return redirect(url_for('workouts.generate_workout'))

    return render_template('generate_workout.html', user=user)


@workouts_bp.route('/cancel_pending_workout', methods=['POST'])
@require_auth
def cancel_pending_workout():
    """Clear pending workout plan from session."""
    session.pop('pending_workout_plan', None)
    session.pop('pending_workout_goal', None)
    return jsonify({'success': True})


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
@require_auth
def update_pending_movement():
    """Update sets/reps/weight for a movement in the pending workout plan."""
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

    # Validate numeric inputs
    try:
        validated = validate_request(PendingWorkoutUpdateInput, {
            'index': index,
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
        workout_json['movements'][index]['sets'] = int(sets)
    if reps is not None:
        workout_json['movements'][index]['reps'] = int(reps)
    if weight is not None:
        workout_json['movements'][index]['weight'] = float(weight)

    session['pending_workout_plan'] = workout_json
    session.modified = True

    return jsonify({'success': True, 'movement': workout_json['movements'][index]})


@workouts_bp.route('/pending_workout/remove_movement/<int:index>', methods=['POST'])
@require_auth
def remove_pending_movement(index):
    """Remove a movement from the pending workout plan."""
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


@workouts_bp.route('/pending_workout/reorder_movement', methods=['POST'])
@require_auth
def reorder_pending_movement():
    """Reorder movements in the pending workout plan."""
    workout_json = session.get('pending_workout_plan')
    if not workout_json:
        return jsonify({'error': 'No pending workout found'}), 404

    data = request.get_json()
    from_index = data.get('from_index')
    to_index = data.get('to_index')

    movements = workout_json.get('movements', [])

    if from_index is None or to_index is None:
        return jsonify({'error': 'Missing from_index or to_index'}), 400

    if from_index < 0 or from_index >= len(movements):
        return jsonify({'error': 'Invalid from_index'}), 400

    if to_index < 0 or to_index >= len(movements):
        return jsonify({'error': 'Invalid to_index'}), 400

    # Swap the movements
    movements[from_index], movements[to_index] = movements[to_index], movements[from_index]

    session['pending_workout_plan'] = workout_json
    session.modified = True

    return jsonify({'success': True})


@workouts_bp.route('/pending_workout/add_movement', methods=['POST'])
@require_auth
def add_pending_movement():
    """Add an existing movement to the pending workout plan."""
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

    workout_json['movements'].append(new_movement)
    session['pending_workout_plan'] = workout_json
    session.modified = True

    return jsonify({'success': True, 'movement': new_movement})


@workouts_bp.route('/pending_workout/add_custom_movement', methods=['POST'])
@require_auth
def add_pending_custom_movement():
    """Add a custom movement to the pending workout plan."""
    workout_json = session.get('pending_workout_plan')
    if not workout_json:
        return jsonify({'error': 'No pending workout found'}), 404

    data = request.get_json()
    movement_name = data.get('movement_name', '').strip()
    sets = data.get('sets', 3)
    reps = data.get('reps', 10)
    weight = data.get('weight', 0)

    if not movement_name:
        return jsonify({'error': 'Movement name is required'}), 400

    # Format movement name to Title Case
    formatted_name = MovementService.format_movement_name(movement_name)

    # Validate numeric inputs
    try:
        validated = validate_request(MovementInput, {
            'movement_name': formatted_name,
            'sets': sets,
            'reps': reps,
            'weight': weight
        })
        sets = validated['sets']
        reps = validated['reps']
        weight = validated['weight']
    except ValidationError as e:
        return jsonify({'error': e.message}), 400

    # Generate muscle group impacts using OpenAI with formatted name
    from app.services.openai_service import generate_movement_info
    try:
        muscle_groups_data = generate_movement_info(formatted_name)
        if not muscle_groups_data:
            # Fallback to empty muscle groups if generation fails
            muscle_groups_data = []
    except Exception as e:
        logger.error(f"Error generating muscle groups for {formatted_name}: {e}")
        muscle_groups_data = []

    new_movement = {
        'name': formatted_name,
        'sets': int(sets),
        'reps': int(reps),
        'weight': float(weight),
        'is_bodyweight': weight == 0,
        'muscle_groups': muscle_groups_data
    }

    workout_json['movements'].append(new_movement)
    session['pending_workout_plan'] = workout_json
    session.modified = True

    return jsonify({'success': True, 'movement': new_movement})

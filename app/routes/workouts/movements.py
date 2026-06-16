"""Movement management on a saved workout (add, remove, AI-fill)."""
from flask import request, redirect, url_for, session, flash

from app.models import Movement, WorkoutMovement, User
from app.services.movement_service import MovementService
from app.services.ai_generation_service import AIGenerationService
from app.services.workout_service import WorkoutService
from app.guards import (
    require_auth,
    rate_limit_llm,
    WorkoutGenerationInput,
    MovementInput,
    ValidationError,
    validate_request,
    ContentFilterError,
)

from app.routes.workouts.blueprint import workouts_bp


@workouts_bp.route('/add_movement', methods=['POST'])
@require_auth
def add_movement():
    from app.guards.rate_limiter import RateLimiter, RateLimitExceeded

    workout_id = request.form.get('workout_id', type=int)
    movement_option = request.form.get('movement_option', 'existing')
    set_count = request.form.get('sets', type=int, default=1)
    reps_per_set = request.form.get('reps_per_set', type=int, default=10)
    weight_value = request.form.get('weight', type=float, default=0.0)

    # Validate numeric inputs
    try:
        validated = validate_request(MovementInput, {
            'movement_name': 'placeholder',  # Will be replaced below
            'sets': set_count,
            'reps': reps_per_set,
            'weight': weight_value
        })
        set_count = validated['sets']
        reps_per_set = validated['reps']
        weight_value = validated['weight']
    except ValidationError as e:
        flash(f"Invalid input: {e.message}", 'error')
        return redirect(url_for('workouts.view_workout', workout_id=workout_id))

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
        # New movement - will fetch muscle groups via AI (rate limited)
        new_movement_name = request.form.get('new_movement_name', '').strip()
        if not new_movement_name:
            flash("No new movement name provided.", "error")
            return redirect(url_for('workouts.view_workout', workout_id=workout_id))

        # Validate movement name
        try:
            validated = validate_request(MovementInput, {
                'movement_name': new_movement_name,
                'sets': set_count,
                'reps': reps_per_set,
                'weight': weight_value
            })
            new_movement_name = validated['movement_name']
        except ValidationError as e:
            flash(f"Invalid input: {e.message}", 'error')
            return redirect(url_for('workouts.view_workout', workout_id=workout_id))

        # Rate limit new movement creation (triggers AI call)
        try:
            RateLimiter.check_and_increment(session['user_id'])
        except RateLimitExceeded as e:
            flash(e.message, 'error')
            return redirect(url_for('workouts.view_workout', workout_id=workout_id))

        try:
            MovementService.add_movement_to_workout(
                workout_id,
                new_movement_name,
                set_count,
                reps_per_set,
                weight_value,
                is_bodyweight=False
            )
        except ContentFilterError as e:
            flash(e.message, "error")
            return redirect(url_for('workouts.view_workout', workout_id=workout_id))

    flash("Movement added to workout!", "success")
    return redirect(url_for('workouts.view_workout', workout_id=workout_id))


@workouts_bp.route('/remove_movement/<int:workout_movement_id>', methods=['POST'])
def remove_movement(workout_movement_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # Authorization check: ensure user owns the workout containing this movement
    workout_movement = WorkoutMovement.query.get_or_404(workout_movement_id)
    if workout_movement.workout.user_id != session['user_id']:
        flash("You don't have permission to modify this workout.", "error")
        return redirect(url_for('main_bp.index')), 403

    workout_id = MovementService.remove_movement_from_workout(workout_movement_id)
    flash("Movement removed from workout.", "info")
    return redirect(url_for('workouts.view_workout', workout_id=workout_id))


@workouts_bp.route('/generate_movements/<int:workout_id>', methods=['POST'])
@require_auth
@rate_limit_llm
def generate_movements(workout_id):
    user = User.query.get(session['user_id'])

    sex = user.sex or request.form.get('sex', 'Unknown')
    weight = user.bodyweight or request.form.get('weight', '70')
    gymexp = user.gym_experience or request.form.get('gymexp', 'beginner')
    target = request.form.get('target', 'general fitness')
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
        return redirect(url_for('workouts.view_workout', workout_id=workout_id))

    try:
        workout_plan = AIGenerationService.generate_single_workout(
            sex, weight, gymexp, target, goal, restrictions,
            user_id=session['user_id']
        )
        WorkoutService.generate_and_add_movements(workout_id, workout_plan)
        flash("Movements generated and added to your workout!", "success")
    except ContentFilterError as e:
        flash(e.message, "error")
    except Exception as e:
        flash(f"Error generating movements: {str(e)}", "error")

    return redirect(url_for('workouts.view_workout', workout_id=workout_id))

"""Workout launch and live-session routes (dashboard entry + active workout)."""
from datetime import date, datetime

from flask import render_template, request, redirect, url_for, session, flash, jsonify

from app.models import Movement, Workout, WorkoutMovement, Set, Rep, Weight, SetEntry, db
from app.services.workout_service import WorkoutService
from app.services.movement_service import MovementService
from app.services.ai_generation_service import AIGenerationService
from app.guards import require_auth, rate_limit_llm, ContentFilterError

from app.routes.workouts.blueprint import workouts_bp, _coerce_to_date


# -----------------------------
# Dashboard / Navigation
# -----------------------------

@workouts_bp.route('/start_workout', methods=['GET'])
def start_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    WorkoutService.cleanup_empty_quick_start_workouts(session['user_id'])
    workouts = WorkoutService.get_user_workouts(session['user_id'])
    today = date.today()

    todays_workouts = [
        w for w in workouts
        if _coerce_to_date(w.workout_date) == today and not w.is_completed
    ]
    recent_workouts = workouts[:30]

    return render_template(
        'start_workout.html',
        workouts=workouts,
        todays_workouts=todays_workouts,
        recent_workouts=recent_workouts,
    )


@workouts_bp.route('/workout/<int:workout_id>/start_now', methods=['POST'])
def start_workout_now(workout_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    try:
        new_workout = WorkoutService.start_workout_now(
            session['user_id'],
            workout_id,
            target_date=date.today()
        )
    except ValueError as e:
        message = str(e)
        if "not found" in message.lower():
            return jsonify({'error': message}), 404
        if "unauthorized" in message.lower():
            return jsonify({'error': message}), 403
        return jsonify({'error': message}), 400

    return jsonify({
        'success': True,
        'workout_id': new_workout.workout_id,
        'duplicated': True
    }), 200


@workouts_bp.route('/workouts/quick_start', methods=['POST'])
def quick_start_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    WorkoutService.cleanup_empty_quick_start_workouts(session['user_id'])
    quick_workout = WorkoutService.create_quick_start_workout(
        session['user_id'],
        workout_date=date.today()
    )
    return jsonify({
        'success': True,
        'workout_id': quick_workout.workout_id
    }), 200


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
# Active Session Tracking
# -----------------------------

@workouts_bp.route('/active_workout/<int:workout_id>', methods=['GET'])
def active_workout(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    workout = Workout.query.get_or_404(workout_id)

    if workout.user_id != session['user_id']:
        flash("Unauthorized access to the workout.", "error")
        return redirect(url_for('main_bp.index'))

    # Move a stale (past) date up to today when actually starting the session;
    # don't silently re-date a today/future or already-completed workout on every open.
    today = date.today()
    workout_day = workout.workout_date
    if isinstance(workout_day, datetime):
        workout_day = workout_day.date()
    if not workout.is_completed and workout_day and workout_day < today:
        WorkoutService.update_workout_date(workout_id, today)

    # Get all movements for the add movement panel
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
        'active_workout.html',
        workout=workout,
        all_movements=movements_with_muscle_groups,
        auto_cleanup_empty_workout=(
            workout.workout_name.startswith("Quick Workout -")
            and len(workout.workout_movements) == 0
        )
    )


@workouts_bp.route('/add_set/<int:workout_movement_id>', methods=['POST'])
@require_auth
def add_set_to_movement(workout_movement_id):
    """Add a new set to a workout movement during an active workout."""
    workout_movement = WorkoutMovement.query.get_or_404(workout_movement_id)

    # Authorization check
    if workout_movement.workout.user_id != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json() or {}

    # Copy defaults from last set if available
    last_set = (
        workout_movement.sets[-1]
        if workout_movement.sets
        else None
    )

    default_reps = data.get('reps', 10)
    default_weight = data.get('weight', 0.0)
    is_bodyweight = data.get('is_bodyweight', False)

    if last_set:
        if last_set.reps:
            default_reps = last_set.reps[0].rep_count
        if last_set.weights:
            default_weight = float(last_set.weights[0].weight_value)
            is_bodyweight = last_set.weights[0].is_bodyweight

    # Determine new set order
    new_set_order = len(workout_movement.sets) + 1

    # Create the new set
    new_set = Set(
        workout_movement_id=workout_movement_id,
        set_order=new_set_order,
        status='pending'
    )
    db.session.add(new_set)
    db.session.flush()

    # Create rep record
    rep_record = Rep(
        set_id=new_set.set_id,
        rep_count=default_reps
    )
    db.session.add(rep_record)

    # Create weight record
    w_record = Weight(
        set_id=new_set.set_id,
        weight_value=default_weight,
        is_bodyweight=is_bodyweight
    )
    db.session.add(w_record)

    # Create paired entry record
    entry_record = SetEntry(
        set_id=new_set.set_id,
        entry_order=1,
        reps=default_reps,
        weight_value=default_weight,
        is_bodyweight=is_bodyweight
    )
    db.session.add(entry_record)
    db.session.commit()

    return jsonify({
        'success': True,
        'set': {
            'setId': new_set.set_id,
            'setOrder': new_set.set_order,
            'reps': default_reps,
            'weight': default_weight,
            'weightId': w_record.weight_id,
            'status': 'pending'
        }
    })


@workouts_bp.route('/active_workout/<int:workout_id>/add_movement', methods=['POST'])
@require_auth
def add_movement_to_active_workout(workout_id):
    """Add a new movement to an active workout."""
    workout = Workout.query.get_or_404(workout_id)

    if workout.user_id != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json()
    movement_id = data.get('movement_id')
    sets = int(data.get('sets', 3))
    reps = int(data.get('reps', 10))
    weight = float(data.get('weight', 0))

    if not movement_id:
        return jsonify({'error': 'Movement ID is required'}), 400

    # Get the movement
    movement = Movement.query.get(movement_id)
    if not movement:
        return jsonify({'error': 'Movement not found'}), 404

    # Create WorkoutMovement
    wm = WorkoutMovement(
        workout_id=workout_id,
        movement_id=movement.movement_id,
        is_completed=False
    )
    db.session.add(wm)
    db.session.flush()

    # Create sets using MovementService pattern
    created_sets = MovementService._create_sets_for_workout_movement(
        wm.workout_movement_id, sets, reps, weight, is_bodyweight=(weight == 0)
    )

    db.session.commit()

    # Return data for UI update
    return jsonify({
        'success': True,
        'movement': {
            'workout_movement_id': wm.workout_movement_id,
            'movementName': movement.movement_name,
            'sets': [
                {
                    'setId': s.set_id,
                    'setOrder': s.set_order,
                    'reps': reps,
                    'weight': weight,
                    'weightId': s.weights[0].weight_id if s.weights else None,
                    'status': 'pending'
                }
                for s in created_sets
            ]
        }
    })


@workouts_bp.route('/active_workout/<int:workout_id>/sets/<int:set_id>/log', methods=['POST'])
@require_auth
def log_active_set(workout_id, set_id):
    """Persist a single set immediately during an active workout (server-authoritative)."""
    single_set = Set.query.get_or_404(set_id)
    if single_set.workout_movement.workout.user_id != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json() or {}
    result = WorkoutService.log_active_set(
        set_id=set_id,
        user_id=session['user_id'],
        reps=data.get('reps'),
        weight=data.get('weight'),
        is_bodyweight=data.get('is_bodyweight'),
        status=data.get('status', 'completed'),
    )
    if result is None:
        return jsonify({'error': 'Unable to log set'}), 400

    return jsonify({'success': True, 'set': result})


@workouts_bp.route('/get_instructions', methods=['GET'])
@require_auth
@rate_limit_llm
def get_instructions():
    movement_name = request.args.get('movement_name', '')
    if not movement_name:
        return jsonify({'error': 'No movement name provided'}), 400

    # Validate movement name length
    if len(movement_name) > 100:
        return jsonify({'error': 'Movement name too long (max 100 characters)'}), 400

    try:
        instructions = AIGenerationService.get_movement_instructions(movement_name)
        return jsonify({'instructions': instructions}), 200
    except ContentFilterError as e:
        return jsonify({'error': e.message}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to fetch instructions'}), 500

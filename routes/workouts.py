# workout_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import json

import nltk
from nltk.stem import WordNetLemmatizer

from init_db import db
from models import Movement, Workout, WorkoutMovement, User, MovementMuscleGroup, MuscleGroup, Weight, Rep, Set, \
    UserGroup, UserGroupMembership
from openai_service import generate_workout_plan, generate_movement_instructions, generate_movement_info

workout_bp = Blueprint('workout_bp', __name__)

lemmatizer = WordNetLemmatizer()

@workout_bp.route('/start_workout', methods=['GET'])
def start_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    user_id = session['user_id']
    workouts = Workout.query.filter_by(user_id=user_id).all()
    return render_template('start_workout.html', workouts=workouts)


@workout_bp.route('/new_workout', methods=['POST'])
def new_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    data = request.get_json()
    if not data or 'workoutDate' not in data:
        return jsonify({'error': 'Invalid data submitted'}), 400

    date_str = data['workoutDate']
    try:
        workout_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    user_id = session['user_id']
    new_w = Workout(
        workout_name="New workout",
        workout_date=workout_date,
        is_completed=False,
        user_id=user_id
    )
    db.session.add(new_w)
    db.session.commit()

    return jsonify({'workout_id': new_w.workout_id}), 200


@workout_bp.route('/select_workout', methods=['GET'])
def select_workout():
    workout_id = request.args.get('workout_id')
    if not workout_id:
        return "No workout selected!"

    workout = Workout.query.get_or_404(workout_id)
    if workout.status == 'planned':
        workout.status = 'started'
        db.session.commit()

    return redirect(url_for('workout_bp.view_workout', workout_id=workout.id))


@workout_bp.route('/select_workout/<int:workout_id>', methods=['GET'])
def select_workout_by_id(workout_id):
    workout = Workout.query.get_or_404(workout_id)

    if workout.status == 'planned':
        workout.status = 'started'
        db.session.commit()

    return redirect(url_for('workout_bp.view_workout', workout_id=workout.id, from_select_workout=True))


@workout_bp.route('/workout/<int:workout_id>', methods=['GET'])
def view_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    date_str = ""
    if workout.workout_date:
        date_str = workout.workout_date.strftime("%Y-%m-%d")

    user_id = session['user_id']
    user = User.query.get(user_id)

    all_movements = Movement.query.all()
    all_movements = sorted(all_movements, key=lambda m: m.movement_name)

    from_select_workout = request.args.get('from_select_workout') == 'True'

    # Prepare muscle groups in a JSON-serializable format
    movements_with_muscle_groups = []
    for movement in all_movements:
        movements_with_muscle_groups.append({
            'movement_id': movement.movement_id,
            'movement_name': movement.movement_name,
            'muscle_groups': [
                {
                    'muscle_group_name': mmg.muscle_group.muscle_group_name,
                    'target_percentage': mmg.target_percentage
                }
                for mmg in movement.muscle_groups
            ]
        })

    muscle_group_impacts = None
    if workout.is_completed:
        aggregate_impacts = {}
        for wm in workout.workout_movements:
            mg_impact_dict = wm.calculate_muscle_group_impact()
            for mg_name, impact_value in mg_impact_dict.items():
                aggregate_impacts[mg_name] = aggregate_impacts.get(mg_name, 0) + impact_value
        muscle_group_impacts = sorted(
            aggregate_impacts.items(),
            key=lambda x: x[1],
            reverse=True
        )

    return render_template(
        'workout_details.html',
        confirm_mode=False,
        workout=workout,
        all_movements=movements_with_muscle_groups,
        from_select_workout=from_select_workout,
        muscle_group_impacts=muscle_group_impacts,
        user=user,
        date_str=date_str
    )


@workout_bp.route('/update_workout_date/<int:workout_id>', methods=['POST'])
def update_workout_date(workout_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    workout = Workout.query.get_or_404(workout_id)
    new_date_str = request.form.get('new_date')

    if not new_date_str:
        flash('Invalid date submitted.', 'error')
        return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))

    try:
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        workout.workout_date = new_date
        db.session.commit()
        flash('Workout date updated successfully.', 'success')
    except ValueError:
        flash('Invalid date format.', 'error')

    return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))


@workout_bp.route('/update_workout_name/<int:workout_id>', methods=['POST'])
def update_workout_name(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    workout = Workout.query.get_or_404(workout_id)
    new_name = request.form.get('workoutName')

    if not new_name:
        return "Workout name cannot be empty.", 400

    workout.workout_name = new_name
    db.session.commit()

    return redirect(url_for('workout_bp.view_workout', workout_id=workout.workout_id))


def normalize_name(name):
    """Normalize movement names by removing plurals using lemmatization."""
    words = name.strip().split()
    normalized_words = [lemmatizer.lemmatize(word) for word in words]
    return " ".join(normalized_words)


@workout_bp.route('/add_movement', methods=['POST'])
def add_movement():
    workout_id = request.form.get('workout_id', type=int)
    workout = Workout.query.get_or_404(workout_id)

    movement_option = request.form.get('movement_option', 'existing')
    set_count = request.form.get('sets', type=int, default=1)
    reps_per_set = request.form.get('reps_per_set', type=int, default=10)
    weight_value = request.form.get('weight', type=float, default=0.0)
    is_bodyweight = False

    movement_obj = None

    if movement_option == 'existing':
        movement_id = request.form.get('movement_id', type=int)
        if movement_id:
            movement_obj = Movement.query.get_or_404(movement_id)
        else:
            flash("No existing movement selected.", "error")
            return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))
    else:
        new_movement_name = request.form.get('new_movement_name', '').strip()
        if not new_movement_name:
            flash("No new movement name provided.", "error")
            return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))

        movement_json = generate_movement_info(new_movement_name)
        is_bodyweight = movement_json.get("is_bodyweight", False)
        weight_value = float(movement_json.get("weight", 0.0))

        movement_name = movement_json.get("movement_name", new_movement_name)
        movement_obj = Movement.query.filter_by(movement_name=movement_name).first()
        if not movement_obj:
            movement_obj = Movement(
                movement_name=movement_name,
                movement_description=""
            )
            db.session.add(movement_obj)
            db.session.commit()

        mg_list = movement_json.get("muscle_groups", [])
        for mg in mg_list:
            mg_name = mg.get("name", "")
            mg_impact = mg.get("impact", 0)
            if not mg_name:
                continue
            mg_obj = MuscleGroup.query.filter_by(muscle_group_name=mg_name).first()
            if not mg_obj:
                mg_obj = MuscleGroup(muscle_group_name=mg_name)
                db.session.add(mg_obj)
                db.session.commit()

            mmg = MovementMuscleGroup.query.filter_by(
                movement_id=movement_obj.movement_id,
                muscle_group_id=mg_obj.muscle_group_id
            ).first()
            if not mmg:
                mmg = MovementMuscleGroup(
                    movement_id=movement_obj.movement_id,
                    muscle_group_id=mg_obj.muscle_group_id,
                    target_percentage=mg_impact
                )
                db.session.add(mmg)
                db.session.commit()

    if not movement_obj:
        flash("Failed to get or create movement.", "error")
        return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))

    wm = WorkoutMovement(
        workout_id=workout_id,
        movement_id=movement_obj.movement_id,
    )
    db.session.add(wm)
    db.session.commit()

    for s_index in range(set_count):
        new_set = Set(
            workout_movement_id=wm.workout_movement_id,
            set_order=s_index + 1
        )
        db.session.add(new_set)
        db.session.commit()

        rep_record = Rep(set_id=new_set.set_id, rep_count=reps_per_set)
        db.session.add(rep_record)
        db.session.commit()

        w_record = Weight(
            set_id=new_set.set_id,
            weight_value=weight_value,
            is_bodyweight=is_bodyweight
        )
        db.session.add(w_record)
        db.session.commit()

    flash("Movement added to workout!", "success")
    return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))


@workout_bp.route('/update_status', methods=['POST'])
def update_status():
    workout_id = request.form.get('workout_id', type=int)
    new_status = request.form.get('status')

    workout = Workout.query.get_or_404(workout_id)
    workout.status = new_status
    db.session.commit()

    return redirect(url_for('workout_bp.view_workout', workout_id=workout.id))


@workout_bp.route('/all_workouts')
def all_workouts():
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    user_id = session['user_id']
    workouts = Workout.query.filter_by(user_id=user_id).all()
    return render_template('all_workouts.html', workouts=workouts)


@workout_bp.route('/generate_workout', methods=['GET', 'POST'])
def generate_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        sex = user.sex or request.form.get('sex', 'Unknown')
        bodyweight = user.bodyweight or request.form.get('weight', 70)
        gymexp = user.gym_experience or request.form.get('gymexp', 'beginner')
        target = request.form.get('target') or session.get('pending_target', 'General Fitness')
        session['pending_workout_plan'] = {}
        session['pending_target'] = target
        max_attempts = 3
        workout_json = None

        for attempt in range(max_attempts):
            try:
                chatgpt_text = generate_workout_plan(sex, bodyweight, gymexp, target)
            except Exception as e:
                flash(f"Error generating workout plan: {str(e)}", 'error')
                return redirect(url_for('workout_bp.generate_workout'))
            try:
                if chatgpt_text.startswith("```") and chatgpt_text.endswith("```"):
                    chatgpt_text = chatgpt_text.strip("```").strip()
                    if chatgpt_text.startswith("json"):
                        chatgpt_text = chatgpt_text[4:].strip()

                chatgpt_text = chatgpt_text.split('```')[0].strip()

                workout_json = json.loads(chatgpt_text)
                session['pending_target'] = workout_json.get("workout_name", "General Fitness")
                break
            except json.JSONDecodeError as e:
                if attempt == max_attempts - 1:
                    flash("Failed to parse JSON from ChatGPT after multiple attempts.", "error")
                    return redirect(url_for('workout_bp.generate_workout'))

        session['pending_workout_plan'] = workout_json
        print(chatgpt_text)
        return redirect(url_for('workout_bp.confirm_workout'))

    else:
        return render_template('generate_workout.html', user=user)


@workout_bp.route('/confirm_workout', methods=['GET', 'POST'])
def confirm_workout():
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    workout_json = session.get('pending_workout_plan')
    if not workout_json:
        flash("No workout plan found to confirm!", 'error')
        return redirect(url_for('workout_bp.generate_workout'))

    if request.method == 'POST':
        user_id = session['user_id']
        workout_name = workout_json.get("workout_name", "Unnamed Workout")
        movements_list = workout_json.get("movements", [])

        new_workout = Workout(
            user_id=user_id,
            workout_name=workout_name,
            workout_date=datetime.now(),
            is_completed=False
        )
        db.session.add(new_workout)
        db.session.commit()

        for m in movements_list:
            movement_name = m.get("name", "Unknown Movement")
            movement_obj = Movement.query.filter_by(
                movement_name=movement_name
            ).first()
            if not movement_obj:
                movement_obj = Movement(
                    movement_name=movement_name,
                    movement_description=m.get("description", "")
                )
                db.session.add(movement_obj)
                db.session.commit()

            wm = WorkoutMovement(
                workout_id=new_workout.workout_id,
                movement_id=movement_obj.movement_id
            )
            db.session.add(wm)
            db.session.commit()

            set_count = m.get("sets", 3)
            reps_per_set = m.get("reps", 10)
            weight_value = float(m.get("weight", 0.0))
            is_bodyweight = bool(m.get("is_bodyweight", False))

            for s_index in range(set_count):
                new_set = Set(
                    workout_movement_id=wm.workout_movement_id,
                    set_order=s_index + 1
                )
                db.session.add(new_set)
                db.session.commit()

                rep_record = Rep(
                    set_id=new_set.set_id,
                    rep_count=reps_per_set
                )
                db.session.add(rep_record)
                db.session.commit()

                w_record = Weight(
                    set_id=new_set.set_id,
                    weight_value=weight_value,
                    is_bodyweight=is_bodyweight
                )
                db.session.add(w_record)
                db.session.commit()

            for mg in m.get("muscle_groups", []):
                mg_name = mg.get("name", "")
                mg_impact = mg.get("impact", 0)
                mg_obj = MuscleGroup.query.filter_by(
                    muscle_group_name=mg_name
                ).first()
                if not mg_obj:
                    mg_obj = MuscleGroup(muscle_group_name=mg_name)
                    db.session.add(mg_obj)
                    db.session.commit()

                from models import MovementMuscleGroup
                mmg_obj = MovementMuscleGroup.query.filter_by(
                    movement_id=movement_obj.movement_id,
                    muscle_group_id=mg_obj.muscle_group_id
                ).first()
                if not mmg_obj:
                    mmg_obj = MovementMuscleGroup(
                        movement_id=movement_obj.movement_id,
                        muscle_group_id=mg_obj.muscle_group_id,
                        target_percentage=mg_impact
                    )
                    db.session.add(mmg_obj)
                    db.session.commit()

        session.pop('pending_workout_plan', None)
        flash("Workout successfully created!", 'success')
        return redirect(url_for('workout_bp.view_workout', workout_id=new_workout.workout_id))
    else:
        return render_template(
            'workout_details.html',
            confirm_mode=True,
            pending_workout=workout_json,
            workout=None
        )


@workout_bp.route('/update_workout/<int:workout_id>', methods=['POST'])
def update_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)

    for wm in workout.workout_movements:
        for s in wm.sets:
            if s.weights:
                w = s.weights[0]
                weight_key = f"weight_{w.weight_id}"
                bodyweight_key = f"is_bodyweight_{w.weight_id}"

                if weight_key in request.form:
                    w.weight_value = float(request.form[weight_key])

                w.is_bodyweight = (bodyweight_key in request.form)

            if s.reps:
                rep = s.reps[0]
                rep_key = f"rep_{s.set_id}"
                if rep_key in request.form:
                    rep.rep_count = int(request.form[rep_key])

    for wm in workout.workout_movements:
        done_key = f"done_{wm.workout_movement_id}"
        wm.done = (done_key in request.form)

    completion_date = request.form.get('completion_date')
    if completion_date:
        # do something if needed
        pass

    db.session.commit()
    flash("Workout updated successfully!", "success")
    return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))


@workout_bp.route('/update_workout_movements', methods=['POST'])
def update_workout_movements():
    workout_id = request.form.get('workout_id', type=int)
    workout = Workout.query.get_or_404(workout_id)

    # Original code was placeholders, do not alter
    for wm in workout.workout_movements:
        wm.sets = request.form.get(f"sets_{wm.id}", type=int, default=wm.sets)
        wm.reps_per_set = request.form.get(f"reps_{wm.id}", type=int, default=wm.reps_per_set)
        wm.weight = request.form.get(f"weight_{wm.id}", type=float, default=wm.weight)

        wm.done = f"done_{wm.id}" in request.form

    db.session.commit()
    flash("Workout movements updated successfully!", "success")
    return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))


@workout_bp.route('/complete_workout', methods=['POST'])
def complete_workout():
    workout_id = request.form.get('workout_id', type=int)
    workout = Workout.query.get_or_404(workout_id)

    completion_date_str = request.form.get('completion_date')
    if completion_date_str:
        try:
            completion_date = datetime.strptime(completion_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "error")
            return redirect(url_for('workout_bp.view_workout', workout_id=workout_id))
    else:
        completion_date = datetime.now().date()

    workout.is_completed = True
    workout.workout_date = completion_date

    for wm in workout.workout_movements:
        wm.done = (f"done_{wm.workout_movement_id}" in request.form)

        for s in wm.sets:
            rep_key = f"rep_{s.set_id}"
            if rep_key in request.form:
                new_rep_count = int(request.form[rep_key])
                if s.reps:
                    s.reps[0].rep_count = new_rep_count

            if s.weights:
                w = s.weights[0]
                weight_key = f"weight_{w.weight_id}"
                if weight_key in request.form:
                    new_weight_value = float(request.form[weight_key])
                    w.weight_value = new_weight_value

    db.session.commit()

    flash("Workout marked as completed!", 'success')
    return redirect(url_for('main_bp.index'))


@workout_bp.route('/get_instructions', methods=['GET'])
def get_instructions():
    movement_name = request.args.get('movement_name', '')
    if not movement_name:
        return jsonify({'error': 'No movement name provided'}), 400

    try:
        instructions = generate_movement_instructions(movement_name)
        return jsonify({'instructions': instructions}), 200
    except Exception as e:
        print(f"Error fetching instructions: {e}")
        return jsonify({'error': 'Failed to fetch instructions'}), 500


@workout_bp.route('/generate_movements/<int:workout_id>', methods=['POST'])
def generate_movements(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    workout = Workout.query.get_or_404(workout_id)

    user = User.query.get(session['user_id'])
    user_sex = user.sex if user and user.sex else None
    user_bodyweight = user.bodyweight if user and user.bodyweight else None
    user_gymexp = user.gym_experience if user and user.gym_experience else None

    sex = user_sex or request.form.get('sex', 'Unknown')
    weight = user_bodyweight or request.form.get('weight', '70')
    gymexp = user_gymexp or request.form.get('gymexp', 'beginner')
    target = request.form.get('target', 'general fitness')

    try:
        chatgpt_text = generate_workout_plan(sex, weight, gymexp, target)
    except Exception as e:
        return f"Error generating workout movements: {str(e)}", 500

    print("ChatGPT Response:", chatgpt_text)

    try:
        if chatgpt_text.startswith("```") and chatgpt_text.endswith("```"):
            chatgpt_text = chatgpt_text.strip("```").strip()
            if chatgpt_text.startswith("json"):
                chatgpt_text = chatgpt_text[4:].strip()
        chatgpt_text = chatgpt_text.split('```')[0].strip()
        workout_json = json.loads(chatgpt_text)
    except json.JSONDecodeError as e:
        print("JSON Decode Error:", e)
        print("Raw ChatGPT Response:", chatgpt_text)
        return "Failed to parse JSON from ChatGPT!", 400

    if "workout_name" in workout_json:
        w_name = workout_json["workout_name"]
        if w_name:
            workout.workout_name = w_name

    movements = workout_json.get("movements", [])
    for m in movements:
        movement_name = m.get("name", "Unknown Movement")
        set_count = m.get("sets", 3)
        reps_per_set = m.get("reps", 10)
        weight_value = float(m.get("weight", 0.0))
        is_bodyweight = bool(m.get("is_bodyweight", False))

        movement_obj = Movement.query.filter_by(movement_name=movement_name).first()
        if not movement_obj:
            movement_obj = Movement(
                movement_name=movement_name,
                movement_description=m.get("description", "")
            )
            db.session.add(movement_obj)
            db.session.commit()

        wm = WorkoutMovement(workout_id=workout.workout_id, movement_id=movement_obj.movement_id)
        db.session.add(wm)
        db.session.commit()

        for s_index in range(set_count):
            new_set = Set(
                workout_movement_id=wm.workout_movement_id,
                set_order=s_index + 1
            )
            db.session.add(new_set)
            db.session.commit()

            rep_record = Rep(set_id=new_set.set_id, rep_count=reps_per_set)
            db.session.add(rep_record)
            db.session.commit()

            w_record = Weight(set_id=new_set.set_id, weight_value=weight_value, is_bodyweight=is_bodyweight)
            db.session.add(w_record)
            db.session.commit()

        muscle_groups = m.get("muscle_groups", [])
        for mg in muscle_groups:
            mg_name = mg.get("name", "")
            mg_impact = mg.get("impact", 0)
            mg_obj = MuscleGroup.query.filter_by(muscle_group_name=mg_name).first()
            if not mg_obj:
                mg_obj = MuscleGroup(muscle_group_name=mg_name)
                db.session.add(mg_obj)
                db.session.commit()

            from models import MovementMuscleGroup
            mmg_obj = MovementMuscleGroup.query.filter_by(
                movement_id=movement_obj.movement_id,
                muscle_group_id=mg_obj.muscle_group_id
            ).first()
            if not mmg_obj:
                mmg_obj = MovementMuscleGroup(
                    movement_id=movement_obj.movement_id,
                    muscle_group_id=mg_obj.muscle_group_id,
                    target_percentage=mg_impact
                )
                db.session.add(mmg_obj)
                db.session.commit()

    db.session.commit()

    flash("Movements generated and added to your workout!", "success")
    return redirect(url_for('workout_bp.view_workout', workout_id=workout.workout_id))


@workout_bp.route('/delete_workout/<int:workout_id>', methods=['POST'])
def delete_workout(workout_id):
    w = Workout.query.get_or_404(workout_id)
    db.session.delete(w)
    db.session.commit()
    flash("Workout has been removed.", "success")
    return redirect(url_for('main_bp.index'))


@workout_bp.route('/remove_movement/<int:workout_movement_id>', methods=['POST'])
def remove_movement(workout_movement_id):
    print("täällä")
    wm = WorkoutMovement.query.get_or_404(workout_movement_id)
    w_id = wm.workout_id

    db.session.delete(wm)
    db.session.commit()

    flash("Movement removed from workout.", "info")
    return redirect(url_for('workout_bp.view_workout', workout_id=w_id))

@workout_bp.route('/active_workout/<int:workout_id>', methods=['GET'])
def active_workout(workout_id):
    """
    Serve the interactive workout page for real-time tracking.
    """
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    workout = Workout.query.get_or_404(workout_id)
    user_id = session['user_id']

    # Ensure the workout belongs to the logged-in user
    if workout.user_id != user_id:
        flash("Unauthorized access to the workout.", "error")
        return redirect(url_for('main_bp.index'))

    return render_template('active_workout.html', workout=workout)


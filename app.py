from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import logging

from models import  Movement, Workout, WorkoutMovement, User, MovementMuscleGroup, MuscleGroup, Weight, Rep, Set, \
    UserGroup, UserGroupMembership
from werkzeug.security import generate_password_hash, check_password_hash
from openai_service import generate_workout_plan, generate_movement_instructions, generate_movement_info
import nltk
from nltk.stem import WordNetLemmatizer
import json
import os
from init_db import init_db

nltk.download('wordnet')
nltk.download('omw-1.4')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")  # Use a secure secret key in production

# Initialize database
if app.config.get("ENV", "development") == "development":
    logger.info("Running in development mode.")
init_db(app)

lemmatizer = WordNetLemmatizer()

# Routes for user authentication
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not password or not email:
            flash('Username, email, and password are required.', 'error')
            return redirect(url_for('register'))

        # Check if the username is taken
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'error')
            return redirect(url_for('register'))

        # Check if the email is taken
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already in use.', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))

        session['user_id'] = user.user_id
        session['username'] = user.username

        flash('Logged in successfully.', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    return render_template('index.html', username=session['username'], user=user)


@app.route('/update_user', methods=['POST'])
def update_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for('index'))

    # Retrieve form fields
    user.email = request.form.get('email', user.email)
    user.first_name = request.form.get('first_name', user.first_name)
    user.last_name = request.form.get('last_name', user.last_name)
    user.sex = request.form.get('sex', user.sex)

    bodyweight_str = request.form.get('bodyweight')
    if bodyweight_str:
        try:
            user.bodyweight = float(bodyweight_str)
        except ValueError:
            flash("Invalid bodyweight input.", "error")

    gym_exp = request.form.get('gym_experience')
    if gym_exp:
        user.gym_experience = gym_exp

    db.session.commit()
    flash("Profile updated successfully!", "success")
    return redirect(url_for('index'))


@app.route('/start_workout', methods=['GET'])
def start_workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    workouts = Workout.query.filter_by(user_id=user_id).all()
    return render_template('start_workout.html', workouts=workouts)


@app.route('/new_workout', methods=['POST'])
def new_workout():
    # Ensure the user is logged in
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    # Parse JSON from the request body
    data = request.get_json()
    if not data or 'workoutDate' not in data:
        return jsonify({'error': 'Invalid data submitted'}), 400

    date_str = data['workoutDate']

    try:
        workout_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    user_id = session['user_id']

    # Create a new workout with a placeholder name
    new_workout = Workout(
        workout_name="New workout",
        workout_date=workout_date,
        is_completed=False,
        user_id=user_id
    )
    db.session.add(new_workout)
    db.session.commit()

    # Return the new workout ID
    return jsonify({'workout_id': new_workout.workout_id}), 200


def get_user_data(user_id):
    user = User.query.get(user_id)
    if not user:
        return None

    user_data = {
        "username": user.username,
        "workouts": []
    }

    for workout in user.workouts:
        workout_data = {
            "workout_name": workout.name,
            "date": workout.date.strftime('%Y-%m-%d'),
            "status": workout.status,
            "movements": []
        }
        for wm in workout.workout_movements:
            workout_data["movements"].append({
                "movement_name": wm.movement.name,
                "sets": wm.sets,
                "reps": wm.reps_per_set,
                "weight": wm.weight,
                "done": wm.done
            })
        user_data["workouts"].append(workout_data)

    return user_data


@app.route('/user_data', methods=['GET'])
def user_data():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get_or_404(user_id)

    # Fetch all workouts associated with the user
    user_workouts = user.workouts
    data = []
    for workout in user_workouts:
        movements = [
            {
                "name": wm.movement.name,
                "sets": wm.sets,
                "reps_per_set": wm.reps_per_set,
                "weight": wm.weight,
                "done": wm.done,
            }
            for wm in workout.workout_movements
        ]
        data.append({
            "workout_id": workout.id,
            "name": workout.name,
            "date": workout.date.strftime('%Y-%m-%d'),
            "status": workout.status,
            "movements": movements,
        })

    return jsonify(data)


@app.route('/select_workout', methods=['GET'])
def select_workout():
    workout_id = request.args.get('workout_id')
    if not workout_id:
        return "No workout selected!"

    workout = Workout.query.get_or_404(workout_id)
    # Mark as started if it's still planned
    if workout.status == 'planned':
        workout.status = 'started'
        db.session.commit()

    return redirect(url_for('view_workout', workout_id=workout.id))


@app.route('/select_workout/<int:workout_id>', methods=['GET'])
def select_workout_by_id(workout_id):
    workout = Workout.query.get_or_404(workout_id)

    # Mark the workout as started if it's still planned
    if workout.status == 'planned':
        workout.status = 'started'
        db.session.commit()

    # Pass the `from=select_workout` parameter to indicate the workflow
    return redirect(url_for('view_workout', workout_id=workout.id, from_select_workout=True))


@app.route('/workout/<int:workout_id>', methods=['GET'])
def view_workout(workout_id):
    # Fetch the workout, or 404 if not found
    workout = Workout.query.get_or_404(workout_id)

    date_str = ""
    if workout.workout_date:  # i.e. a datetime.date or datetime.datetime
        date_str = workout.workout_date.strftime("%Y-%m-%d")

    user_id = session['user_id']
    user = User.query.get(user_id)

    # Get all movements for the "Add Movement" dropdown
    all_movements = Movement.query.all()
    # Sort movements alphabetically
    all_movements = sorted(all_movements, key=lambda m: m.movement_name)

    from_select_workout = request.args.get('from_select_workout') == 'True'

    # Prepare muscle groups in a JSON-serializable format for the template
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

    # If workout is completed, calculate total muscle group impact
    muscle_group_impacts = None
    if workout.is_completed:
        aggregate_impacts = {}
        for wm in workout.workout_movements:
            # Use the built-in method from the model to get a dict: { "Chest": value, ... }
            mg_impact_dict = wm.calculate_muscle_group_impact()
            for mg_name, impact_value in mg_impact_dict.items():
                aggregate_impacts[mg_name] = aggregate_impacts.get(mg_name, 0) + impact_value

        # Sort muscle groups by total impact (descending)
        muscle_group_impacts = sorted(
            aggregate_impacts.items(),
            key=lambda x: x[1],
            reverse=True
        )

    # Render the workout_details.html template
    return render_template(
        'workout_details.html',
        confirm_mode=False,  # This indicates we're NOT in "confirmation" mode
        workout=workout,
        all_movements=movements_with_muscle_groups,
        from_select_workout=from_select_workout,
        muscle_group_impacts=muscle_group_impacts,
        user=user,
        date_str=date_str
    )


# return render_template(
#    'workout_details.html',
#   confirm_mode=False,
#  workout=some_workout_object,
# from_select_workout=True,  # or False, as needed
# muscle_group_impacts=some_data
# etc.
# )


@app.route('/update_workout_date/<int:workout_id>', methods=['POST'])
def update_workout_date(workout_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    workout = Workout.query.get_or_404(workout_id)
    new_date_str = request.form.get('new_date')

    if not new_date_str:
        flash('Invalid date submitted.', 'error')
        return redirect(url_for('view_workout', workout_id=workout_id))

    try:
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        workout.workout_date = new_date
        db.session.commit()
        flash('Workout date updated successfully.', 'success')
    except ValueError:
        flash('Invalid date format.', 'error')

    return redirect(url_for('view_workout', workout_id=workout_id))


@app.route('/update_workout_name/<int:workout_id>', methods=['POST'])
def update_workout_name(workout_id):
    # Ensure the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the workout and new name
    workout = Workout.query.get_or_404(workout_id)
    new_name = request.form.get('workoutName')

    if not new_name:
        return "Workout name cannot be empty.", 400

    # Update the workout name
    workout.workout_name = new_name
    db.session.commit()

    return redirect(url_for('view_workout', workout_id=workout.workout_id))


def normalize_name(name):
    """Normalize movement names by removing plurals using lemmatization."""
    words = name.strip().split()  # Split the name into words
    normalized_words = [lemmatizer.lemmatize(word) for word in words]  # Lemmatize each word
    return " ".join(normalized_words)  # Join back into a single string


@app.route('/add_movement', methods=['POST'])
def add_movement():
    workout_id = request.form.get('workout_id', type=int)
    workout = Workout.query.get_or_404(workout_id)

    movement_option = request.form.get('movement_option', 'existing')  # 'existing' or 'new'
    set_count = request.form.get('sets', type=int, default=1)
    reps_per_set = request.form.get('reps_per_set', type=int, default=10)
    weight_value = request.form.get('weight', type=float, default=0.0)
    is_bodyweight = False  # or read from form if you want

    movement_obj = None

    if movement_option == 'existing':
        # Existing movement flow
        movement_id = request.form.get('movement_id', type=int)
        if movement_id:
            movement_obj = Movement.query.get_or_404(movement_id)
        else:
            flash("No existing movement selected.", "error")
            return redirect(url_for('view_workout', workout_id=workout_id))

    else:
        # New movement flow
        new_movement_name = request.form.get('new_movement_name', '').strip()
        if not new_movement_name:
            flash("No new movement name provided.", "error")
            return redirect(url_for('view_workout', workout_id=workout_id))

        # 1) Call ChatGPT to get muscle group data for this new movement

        movement_json = generate_movement_info(new_movement_name)
        is_bodyweight = movement_json.get("is_bodyweight", False)
        weight_value = float(movement_json.get("weight", 0.0))

        # 2) Create the Movement in DB
        movement_name = movement_json.get("movement_name", new_movement_name)
        movement_obj = Movement.query.filter_by(movement_name=movement_name).first()
        if not movement_obj:
            movement_obj = Movement(
                movement_name=movement_name,
                movement_description=""
            )
            db.session.add(movement_obj)
            db.session.commit()

        # 3) Create MovementMuscleGroup rows
        mg_list = movement_json.get("muscle_groups", [])
        for mg in mg_list:
            mg_name = mg.get("name", "")
            mg_impact = mg.get("impact", 0)

            if not mg_name:
                continue

            # Find or create the muscle group
            mg_obj = MuscleGroup.query.filter_by(muscle_group_name=mg_name).first()
            if not mg_obj:
                mg_obj = MuscleGroup(muscle_group_name=mg_name)
                db.session.add(mg_obj)
                db.session.commit()

            # Link them in MovementMuscleGroup
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

    # Now 'movement_obj' should exist, whether from existing or new
    if not movement_obj:
        flash("Failed to get or create movement.", "error")
        return redirect(url_for('view_workout', workout_id=workout_id))

    # 4) Create the new WorkoutMovement
    wm = WorkoutMovement(
        workout_id=workout_id,
        movement_id=movement_obj.movement_id,
    )
    db.session.add(wm)
    db.session.commit()  # So wm has an ID

    # 5) Create the specified number of Sets
    for s_index in range(set_count):
        new_set = Set(
            workout_movement_id=wm.workout_movement_id,
            set_order=s_index + 1
        )
        db.session.add(new_set)
        db.session.commit()  # commit so set_id is assigned

        # Create one Rep entry for this set
        rep_record = Rep(
            set_id=new_set.set_id,
            rep_count=reps_per_set
        )
        db.session.add(rep_record)
        db.session.commit()

        # Create one Weight entry for this set
        w_record = Weight(
            set_id=new_set.set_id,
            weight_value=weight_value,
            is_bodyweight=is_bodyweight
        )
        db.session.add(w_record)
        db.session.commit()

    flash("Movement added to workout!", "success")
    return redirect(url_for('view_workout', workout_id=workout_id))



@app.route('/update_status', methods=['POST'])
def update_status():
    workout_id = request.form.get('workout_id', type=int)
    new_status = request.form.get('status')

    workout = Workout.query.get_or_404(workout_id)
    workout.status = new_status
    db.session.commit()

    return redirect(url_for('view_workout', workout_id=workout.id))


@app.route('/all_workouts')
def all_workouts():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    workouts = Workout.query.filter_by(user_id=user_id).all()
    return render_template('all_workouts.html', workouts=workouts)


@app.route('/generate_workout', methods=['GET', 'POST'])
def generate_workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        # 1) Pull user data from DB
        user_sex = user.sex
        user_bodyweight = user.bodyweight
        user_gymexp = user.gym_experience

        # 2) Fall back to form data if DB fields are not set
        sex = user_sex if user_sex else request.form.get('sex', 'Unknown')
        bodyweight = user_bodyweight if user_bodyweight else request.form.get('weight', '70')
        gymexp = user_gymexp if user_gymexp else request.form.get('gymexp', 'beginner')

        target = request.form.get('target', 'general fitness')

        max_attempts = 3
        workout_json = None

        # 3) Generate workout plan (ChatGPT)
        for attempt in range(max_attempts):
            try:
                chatgpt_text = generate_workout_plan(sex, bodyweight, gymexp, target)
            except Exception as e:
                flash(f"Error generating workout plan: {str(e)}", 'error')
                return redirect(url_for('generate_workout'))

            # Try parsing JSON
            try:
                # Strip code fences if present
                if chatgpt_text.startswith("```") and chatgpt_text.endswith("```"):
                    chatgpt_text = chatgpt_text.strip("```").strip()
                    if chatgpt_text.startswith("json"):
                        chatgpt_text = chatgpt_text[4:].strip()

                chatgpt_text = chatgpt_text.split('```')[0].strip()

                workout_json = json.loads(chatgpt_text)
                # If we reach here, parse was successful
                break
            except json.JSONDecodeError as e:
                app.logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
                app.logger.warning(f"Raw ChatGPT response:\n{chatgpt_text}\n")
                # If this was the last attempt, fail
                if attempt == max_attempts - 1:
                    flash("Failed to parse JSON from ChatGPT after multiple attempts.", "error")
                    return redirect(url_for('generate_workout'))
                # Otherwise, loop again (re-call ChatGPT)

        # 4) Store the plan in the session if parse succeeded
        session['pending_workout_plan'] = workout_json
        print(chatgpt_text)
        return redirect(url_for('confirm_workout'))

    else:
        # GET request -> show a form to let user provide/override sex, weight, gymexp, target
        return render_template('generate_workout.html', user=user)


@app.route('/confirm_workout', methods=['GET', 'POST'])
def confirm_workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Attempt to load the pending plan from session
    workout_json = session.get('pending_workout_plan')
    if not workout_json:
        flash("No workout plan found to confirm!", 'error')
        return redirect(url_for('generate_workout'))

    if request.method == 'POST':
        # User clicked "Confirm" -> Save to DB
        user_id = session['user_id']

        # Extract basic info
        workout_name = workout_json.get("workout_name", "Unnamed Workout")
        movements_list = workout_json.get("movements", [])

        # Create a new workout
        new_workout = Workout(
            user_id=user_id,
            workout_name=workout_name,
            workout_date=datetime.now(),
            is_completed=False
        )
        db.session.add(new_workout)
        db.session.commit()  # commit so new_workout has an ID

        # For each movement in the plan
        for m in movements_list:
            movement_name = m.get("name", "Unknown Movement")

            # Find or create Movement
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

            # Create WorkoutMovement
            wm = WorkoutMovement(
                workout_id=new_workout.workout_id,
                movement_id=movement_obj.movement_id
            )
            db.session.add(wm)
            db.session.commit()  # commit so wm has an ID

            # If your ChatGPT plan says something like "sets": 3, "reps": 10, "weight": 50
            # you might do something like this to create actual "Set" + "Rep" + "Weight" entries
            set_count = m.get("sets", 3)
            reps_per_set = m.get("reps", 10)
            weight_value = float(m.get("weight", 0.0))
            is_bodyweight = bool(m.get("is_bodyweight", False))

            # Example: create X sets
            for s_index in range(set_count):
                new_set = Set(
                    workout_movement_id=wm.workout_movement_id,
                    set_order=s_index + 1  # 1-based
                )
                db.session.add(new_set)
                db.session.commit()

                # Create a single Rep entry with reps_per_set
                rep_record = Rep(
                    set_id=new_set.set_id,
                    rep_count=reps_per_set
                )
                db.session.add(rep_record)
                db.session.commit()

                # Create a single Weight entry
                w_record = Weight(
                    set_id=new_set.set_id,
                    weight_value=weight_value,
                    is_bodyweight=is_bodyweight
                )
                db.session.add(w_record)
                db.session.commit()

            # If you have muscle group data, you can store them in MovementMuscleGroup
            # e.g. "muscle_groups": [{"name": "Chest", "impact": 70}, ...]
            for mg in m.get("muscle_groups", []):
                mg_name = mg.get("name", "")
                mg_impact = mg.get("impact", 0)

                # Find or create muscle group
                mg_obj = MuscleGroup.query.filter_by(
                    muscle_group_name=mg_name
                ).first()
                if not mg_obj:
                    mg_obj = MuscleGroup(muscle_group_name=mg_name)
                    db.session.add(mg_obj)
                    db.session.commit()

                # See if MovementMuscleGroup row already exists:
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

        # Clear session data to avoid re-confirming
        session.pop('pending_workout_plan', None)

        flash("Workout successfully created!", 'success')
        return redirect(url_for('view_workout', workout_id=new_workout.workout_id))
    else:
        # GET request -> show user the plan for final confirmation
        return render_template(
            'workout_details.html',
            confirm_mode=True,
            pending_workout=workout_json,
            workout=None  # No real DB workout object yet
        )


@app.route('/update_workout/<int:workout_id>', methods=['POST'])
def update_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)

    # 1) Update sets/reps/weights
    for wm in workout.workout_movements:
        for s in wm.sets:
            # If there's exactly one Weight row, handle that
            if s.weights:
                w = s.weights[0]
                # e.g. "weight_12" if weight_id=12
                weight_key = f"weight_{w.weight_id}"
                bodyweight_key = f"is_bodyweight_{w.weight_id}"

                if weight_key in request.form:
                    w.weight_value = float(request.form[weight_key])

                # if the checkbox is not present => false
                w.is_bodyweight = (bodyweight_key in request.form)

            # Reps
            if s.reps:
                rep = s.reps[0]
                rep_key = f"rep_{s.set_id}"
                if rep_key in request.form:
                    rep.rep_count = int(request.form[rep_key])

    # 2) Check if any movements are "done"
    for wm in workout.workout_movements:
        done_key = f"done_{wm.workout_movement_id}"
        wm.done = (done_key in request.form)

    # Optionally, handle completion date if needed
    completion_date = request.form.get('completion_date')
    if completion_date:
        # set it or ignore if you want partial
        pass

    db.session.commit()
    flash("Workout updated successfully!", "success")
    return redirect(url_for('view_workout', workout_id=workout_id))


@app.route('/update_workout_movements', methods=['POST'])
def update_workout_movements():
    workout_id = request.form.get('workout_id', type=int)
    workout = Workout.query.get_or_404(workout_id)

    for wm in workout.workout_movements:
        # Update actual sets, reps, and weights
        wm.sets = request.form.get(f"sets_{wm.id}", type=int, default=wm.sets)
        wm.reps_per_set = request.form.get(f"reps_{wm.id}", type=int, default=wm.reps_per_set)
        wm.weight = request.form.get(f"weight_{wm.id}", type=float, default=wm.weight)

        # Update "done" status
        wm.done = f"done_{wm.id}" in request.form

    db.session.commit()
    flash("Workout movements updated successfully!", "success")
    return redirect(url_for('view_workout', workout_id=workout_id))


@app.route('/complete_workout', methods=['POST'])
def complete_workout():
    workout_id = request.form.get('workout_id', type=int)
    workout = Workout.query.get_or_404(workout_id)

    # Get the completion date from the form
    completion_date_str = request.form.get('completion_date')
    if completion_date_str:
        try:
            completion_date = datetime.strptime(completion_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "error")
            return redirect(url_for('view_workout', workout_id=workout_id))
    else:
        completion_date = datetime.now().date()  # Default to today's date if not provided

    # Mark the workout as completed
    workout.is_completed = True
    workout.date = completion_date

    # Update all workout movements
    for wm in workout.workout_movements:
        # Is the user marking this entire movement as done?
        wm.done = (f"done_{wm.workout_movement_id}" in request.form)

        # Then update each set for this movement
        for s in wm.sets:
            rep_key = f"rep_{s.set_id}"
            if rep_key in request.form:
                new_rep_count = int(request.form[rep_key])
                # If we assume only 1 Rep record per set:
                if s.reps:
                    s.reps[0].rep_count = new_rep_count

            # If we store weight in s.weights
            if s.weights:
                w = s.weights[0]
                weight_key = f"weight_{w.weight_id}"
                if weight_key in request.form:
                    new_weight_value = float(request.form[weight_key])
                    w.weight_value = new_weight_value
            # else: optionally create a new Weight row if you want to handle that

    db.session.commit()

    flash("Workout marked as completed!", "success")
    return redirect(url_for('index'))


@app.route('/get_instructions', methods=['GET'])
def get_instructions():
    movement_name = request.args.get('movement_name', '')

    if not movement_name:
        return jsonify({'error': 'No movement name provided'}), 400

    try:
        # Fetch instructions using the OpenAI service
        instructions = generate_movement_instructions(movement_name)
        return jsonify({'instructions': instructions}), 200
    except Exception as e:
        print(f"Error fetching instructions: {e}")
        return jsonify({'error': 'Failed to fetch instructions'}), 500


@app.route('/generate_movements/<int:workout_id>', methods=['POST'])
def generate_movements(workout_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Retrieve the existing workout
    workout = Workout.query.get_or_404(workout_id)

    # Optionally, retrieve user data for fallback values
    user = User.query.get(session['user_id'])
    user_sex = user.sex if user and user.sex else None
    user_bodyweight = user.bodyweight if user and user.bodyweight else None
    user_gymexp = user.gym_experience if user and user.gym_experience else None

    # Form data or fallback from user
    sex = user_sex or request.form.get('sex', 'Unknown')
    weight = user_bodyweight or request.form.get('weight', '70')
    gymexp = user_gymexp or request.form.get('gymexp', 'beginner')
    target = request.form.get('target', 'general fitness')

    # Generate the workout plan
    try:
        chatgpt_text = generate_workout_plan(sex, weight, gymexp, target)
    except Exception as e:
        return f"Error generating workout movements: {str(e)}", 500

    print("ChatGPT Response:", chatgpt_text)

    # Parse ChatGPT response
    try:
        # Remove backticks if present
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

    # Update the workout's name if provided
    if "workout_name" in workout_json:
        workout_name = workout_json["workout_name"]
        if workout_name:
            workout.workout_name = workout_name  # or just 'name' if that's your column

    # Go through each movement in the JSON
    movements = workout_json.get("movements", [])
    for m in movements:
        movement_name = m.get("name", "Unknown Movement")

        # For how many sets, reps, weight?
        set_count = m.get("sets", 3)
        reps_per_set = m.get("reps", 10)
        weight_value = float(m.get("weight", 0.0))
        is_bodyweight = bool(m.get("is_bodyweight", False))

        # Find or create Movement
        movement_obj = Movement.query.filter_by(movement_name=movement_name).first()
        if not movement_obj:
            movement_obj = Movement(
                movement_name=movement_name,
                movement_description=m.get("description", "")
            )
            db.session.add(movement_obj)
            db.session.commit()

        # Link Movement to the WorkoutMovement
        wm = WorkoutMovement(
            workout_id=workout.workout_id,
            movement_id=movement_obj.movement_id
        )
        db.session.add(wm)
        db.session.commit()  # So wm has an ID

        # Create the "sets" for this movement
        for s_index in range(set_count):
            new_set = Set(
                workout_movement_id=wm.workout_movement_id,
                set_order=s_index + 1  # 1-based index
            )
            db.session.add(new_set)
            db.session.commit()

            # Create one Rep record
            rep_record = Rep(
                set_id=new_set.set_id,
                rep_count=reps_per_set
            )
            db.session.add(rep_record)
            db.session.commit()

            # Create one Weight record
            w_record = Weight(
                set_id=new_set.set_id,
                weight_value=weight_value,
                is_bodyweight=is_bodyweight
            )
            db.session.add(w_record)
            db.session.commit()

        # Process muscle groups from ChatGPT
        muscle_groups = m.get("muscle_groups", [])
        for mg in muscle_groups:
            mg_name = mg.get("name", "")
            mg_impact = mg.get("impact", 0)

            # Find or create muscle group
            mg_obj = MuscleGroup.query.filter_by(muscle_group_name=mg_name).first()
            if not mg_obj:
                mg_obj = MuscleGroup(
                    muscle_group_name=mg_name
                )
                db.session.add(mg_obj)
                db.session.commit()

            # Link them in MovementMuscleGroup
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
    return redirect(url_for('view_workout', workout_id=workout.workout_id))


@app.route('/delete_workout/<int:workout_id>', methods=['POST'])
def delete_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    db.session.delete(workout)
    db.session.commit()
    flash("Workout has been removed.", "success")
    return redirect(url_for('index'))  # Redirect to home or desired page


@app.route('/remove_movement/<int:workout_movement_id>', methods=['POST'])
def remove_movement(workout_movement_id):
    print("täällä")
    wm = WorkoutMovement.query.get_or_404(workout_movement_id)
    workout_id = wm.workout_id

    # Cascade deletes if you want to remove sets, reps, weights automatically,
    # or manually delete them. Then delete the WorkoutMovement row:
    db.session.delete(wm)
    db.session.commit()

    flash("Movement removed from workout.", "info")
    return redirect(url_for('view_workout', workout_id=workout_id))


@app.route('/historical_data/<muscle_group>', methods=['GET'])
def historical_data(muscle_group):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    # Get historical data for the muscle group
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

    # Sort by date for consistency
    historical_data.sort(key=lambda x: x['date'])

    return jsonify(historical_data)


@app.route('/stats', methods=['GET'])
def stats():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Get the time filter from the query parameter: 'weekly', 'monthly', or 'all'
    time_filter = request.args.get('time_filter', 'all')
    current_date = datetime.now().date()

    # Decide how many days to look back for the current and previous periods
    if time_filter == 'weekly':
        period_length = 7
    elif time_filter == 'monthly':
        period_length = 30
    else:  # 'all' (we'll default to 30 days for current vs. the previous 30 days)
        period_length = 30

    # Calculate date boundaries
    current_start_date = current_date - timedelta(days=period_length)
    previous_start_date = current_start_date - timedelta(days=period_length)

    # Query for workouts in the current period
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

    # Query for workouts in the previous period
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
        """Sum all muscle-group impacts across the given workouts."""
        workloads = {}
        for workout in workouts:
            for wm in workout.workout_movements:
                # WorkoutMovement has calculate_muscle_group_impact()
                mg_impacts = wm.calculate_muscle_group_impact()
                # mg_impacts is a dict { "Chest": x.xx, "Triceps": y.yy, ... }
                for mg_name, impact_value in mg_impacts.items():
                    workloads[mg_name] = workloads.get(mg_name, 0) + impact_value
        return workloads

    # Calculate the muscle group workloads for current and previous periods
    current_values = calculate_workloads(current_workouts)
    previous_values = calculate_workloads(previous_workouts)

    # Figure out the percentage changes for each muscle group
    muscle_group_changes = []
    for mg_name, current_value in current_values.items():
        previous_value = previous_values.get(mg_name, 0)
        if previous_value > 0:
            change = ((current_value - previous_value) / previous_value) * 100.0
        else:
            # If previous_value == 0 but current_value > 0, treat that as 100% improvement (arbitrary decision)
            change = 100.0 if current_value > 0 else 0.0

        muscle_group_changes.append(
            (mg_name, round(current_value, 2), round(change, 2))
        )

    # Sort by absolute percentage change, get the top 5
    top_changes = sorted(
        muscle_group_changes,
        key=lambda x: abs(x[2]),
        reverse=True
    )[:5]

    # Convert to dict for easier use in the template
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


if __name__ == "__main__":
    app.run(debug=True)

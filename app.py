from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from models import db, Movement, Workout, WorkoutMovement, User, MovementMuscleGroup, MuscleGroup
from werkzeug.security import generate_password_hash, check_password_hash
from openai_service import generate_workout_plan, generate_movement_instructions
import nltk
from nltk.stem import WordNetLemmatizer
import json
from sqlalchemy.sql import func

nltk.download('wordnet')
nltk.download('omw-1.4')

lemmatizer = WordNetLemmatizer()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey'  # Replace with a proper secret key

db.init_app(app)


# Routes for user authentication
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
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

        session['user_id'] = user.id
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
    return render_template('index.html', username=session['username'])



@app.route('/start_workout', methods=['GET'])
def start_workout():
    # Show all workouts
    workouts = Workout.query.all()
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
        name="New workout",
        date=workout_date,
        status='planned',
        user_id=user_id
    )
    db.session.add(new_workout)
    db.session.commit()

    # Return the new workout ID
    return jsonify({'workout_id': new_workout.id}), 200




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
    # Fetch the workout and all movements
    workout = Workout.query.get_or_404(workout_id)
    all_movements = Movement.query.all()

    # Sort movements alphabetically by name
    all_movements = sorted(all_movements, key=lambda m: m.name)

    from_select_workout = request.args.get('from_select_workout') == 'True'

    # Prepare muscle groups in JSON-serializable format
    movements_with_muscle_groups = []
    for movement in all_movements:
        movements_with_muscle_groups.append({
            'id': movement.id,
            'name': movement.name,
            'muscle_groups': [
                {
                    'name': mmg.muscle_group.name,
                    'impact': mmg.impact
                }
                for mmg in movement.muscle_groups
            ]
        })

    # Calculate muscle group impacts if workout is completed
    muscle_group_impacts = None
    if workout.status == 'completed':
        muscle_group_impacts = {}
        for wm in workout.workout_movements:
            for mg in wm.movement.muscle_groups:
                impact_volume = wm.sets * wm.reps_per_set * wm.weight * (mg.impact / 100)
                muscle_group_name = mg.muscle_group.name
                muscle_group_impacts[muscle_group_name] = (
                    muscle_group_impacts.get(muscle_group_name, 0) + impact_volume
                )

        # Convert to a list of tuples sorted by impact
        muscle_group_impacts = sorted(
            muscle_group_impacts.items(), key=lambda x: x[1], reverse=True
        )

    return render_template(
        'workout_details.html',
        workout=workout,
        all_movements=movements_with_muscle_groups,
        from_select_workout=from_select_workout,
        muscle_group_impacts=muscle_group_impacts
    )




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
        workout.date = new_date
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
    workout.name = new_name
    db.session.commit()

    return redirect(url_for('view_workout', workout_id=workout.id))


def normalize_name(name):
    """Normalize movement names by removing plurals using lemmatization."""
    words = name.strip().split()  # Split the name into words
    normalized_words = [lemmatizer.lemmatize(word) for word in words]  # Lemmatize each word
    return " ".join(normalized_words)  # Join back into a single string


@app.route('/add_movement', methods=['POST'])
def add_movement():
    workout_id = request.form.get('workout_id', type=int)
    workout = Workout.query.get_or_404(workout_id)

    # Update existing movements' done state
    for wm in workout.workout_movements:
        done_key = f"done_{wm.id}"
        wm.done = request.form.get(done_key) == "true"

    # Add new movement logic
    movement_id = request.form.get('movement_id', type=int)
    sets = request.form.get('sets', type=int, default=1)
    reps = request.form.get('reps_per_set', type=int, default=10)
    weight = request.form.get('weight', type=float, default=0.0)

    if movement_id:
        movement = Movement.query.get_or_404(movement_id)

        # Add the movement to the workout
        new_workout_movement = WorkoutMovement(
            workout_id=workout_id,
            movement_id=movement_id,
            sets=sets,
            reps_per_set=reps,
            weight=weight,
        )
        db.session.add(new_workout_movement)

        # Calculate and log impacts for each muscle group
        for muscle_group_assoc in movement.muscle_groups:
            muscle_group = muscle_group_assoc.muscle_group
            impact_value = (
                    muscle_group_assoc.impact * sets * reps * weight
            )  # Weighted impact calculation
            print(f"Impact on {muscle_group.name}: {impact_value:.2f}")

    db.session.commit()

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
    workouts = Workout.query.all()
    return render_template('all_workouts.html', workouts=workouts)


@app.route('/generate_workout', methods=['GET', 'POST'])
def generate_workout():
    if request.method == 'POST':
        # Check for user session
        if 'user_id' not in session:
            return redirect(url_for('login'))

        # Collect user inputs
        sex = request.form.get('sex')
        weight = request.form.get('weight')
        gymexp = request.form.get('gymexp')
        target = request.form.get('target')

        # Generate the workout plan
        try:
            chatgpt_text = generate_workout_plan(sex, weight, gymexp, target)
        except Exception as e:
            return f"Error generating workout plan: {str(e)}", 500

        print("ChatGPT Response:", chatgpt_text)

        # Parse the response and save the workout
        try:
            # Extract JSON-like text from the response
            if chatgpt_text.startswith("```") and chatgpt_text.endswith("```"):
                chatgpt_text = chatgpt_text.strip("```").strip()
                if chatgpt_text.startswith("json"):
                    chatgpt_text = chatgpt_text[4:].strip()

            chatgpt_text = chatgpt_text.split('```')[0].strip()  # Split and take only JSON
            workout_json = json.loads(chatgpt_text)
        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)
            print("Raw ChatGPT Response:", chatgpt_text)
            return "Failed to parse JSON from ChatGPT!", 400

        user_id = session['user_id']
        workout_name = workout_json.get("workout_name", "Unnamed Workout")
        movements = workout_json.get("movements", [])

        # Create a new workout
        new_workout = Workout(
            name=workout_name,
            date=datetime.now().date(),
            status='planned',
            user_id=user_id
        )
        db.session.add(new_workout)
        db.session.commit()

        # Process each movement
        for m in movements:
            name = m.get("name", "Unknown Movement")
            sets = m.get("sets", 3)
            reps = m.get("reps", 10)
            weight = float(m.get("weight", 0.0))
            muscle_groups = m.get("muscle_groups", [])

            # Find or create the movement
            movement_obj = Movement.query.filter_by(name=name).first()
            if not movement_obj:
                movement_obj = Movement(name=name)
                db.session.add(movement_obj)
                db.session.commit()

            # Create the WorkoutMovement relationship
            wm = WorkoutMovement(
                workout_id=new_workout.id,
                movement_id=movement_obj.id,
                sets=sets,
                reps_per_set=reps,
                weight=weight
            )
            db.session.add(wm)

            # Process muscle groups
            for mg in muscle_groups:
                muscle_group_name = mg.get("name")
                impact = float(mg.get("impact", 0.0))

                # Find or create the muscle group
                muscle_group_obj = MuscleGroup.query.filter_by(name=muscle_group_name).first()
                if not muscle_group_obj:
                    muscle_group_obj = MuscleGroup(name=muscle_group_name)
                    db.session.add(muscle_group_obj)
                    db.session.commit()

                # Create the MovementMuscleGroup relationship
                mmg = MovementMuscleGroup(
                    movement_id=movement_obj.id,
                    muscle_group_id=muscle_group_obj.id,
                    impact=impact
                )
                db.session.add(mmg)

        db.session.commit()

        return redirect(url_for('view_workout', workout_id=new_workout.id))
    else:
        # Render the workout generation form
        return render_template('generate_workout.html')



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

    workout.completion_date = completion_date

    # Update all workout movements
    for wm in workout.workout_movements:
        sets = request.form.get(f"sets_{wm.id}", type=int)
        reps = request.form.get(f"reps_{wm.id}", type=int)
        weight = request.form.get(f"weight_{wm.id}", type=float)
        wm.sets = sets if sets is not None else wm.sets
        wm.reps_per_set = reps if reps is not None else wm.reps_per_set
        wm.weight = weight if weight is not None else wm.weight
        wm.done = f"done_{wm.id}" in request.form

    # Check if all movements are marked as done
    all_done = all(wm.done for wm in workout.workout_movements)
    if not all_done:
        flash("Please mark all movements as done before completing the workout!", "error")
        return redirect(url_for('view_workout', workout_id=workout_id))

    # Mark the workout as completed
    workout.status = "completed"
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

    # Collect user inputs
    sex = request.form.get('sex')
    weight = request.form.get('weight')
    gymexp = request.form.get('gymexp')
    target = request.form.get('target')

    # Generate the workout plan
    try:
        chatgpt_text = generate_workout_plan(sex, weight, gymexp, target)
    except Exception as e:
        return f"Error generating workout movements: {str(e)}", 500

    print("ChatGPT Response:", chatgpt_text)

    # Parse the response and extract movements
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

    # Update the workout name if provided
    workout_name = workout_json.get("workout_name")
    if workout_name:
        workout.name = workout_name

    movements = workout_json.get("movements", [])

    # Add movements to the existing workout
    for m in movements:
        name = m.get("name", "Unknown Movement")
        sets = m.get("sets", 3)
        reps = m.get("reps", 10)
        weight = float(m.get("weight", 0.0))
        muscle_groups = m.get("muscle_groups", [])

        # Find or create the movement
        movement_obj = Movement.query.filter_by(name=name).first()
        if not movement_obj:
            movement_obj = Movement(name=name)
            db.session.add(movement_obj)
            db.session.commit()

        # Create the WorkoutMovement relationship
        wm = WorkoutMovement(
            workout_id=workout.id,
            movement_id=movement_obj.id,
            sets=sets,
            reps_per_set=reps,
            weight=weight
        )
        db.session.add(wm)

        # Process muscle groups
        for mg in muscle_groups:
            muscle_group_name = mg.get("name")
            impact = float(mg.get("impact", 0.0))

            # Find or create the muscle group
            muscle_group_obj = MuscleGroup.query.filter_by(name=muscle_group_name).first()
            if not muscle_group_obj:
                muscle_group_obj = MuscleGroup(name=muscle_group_name)
                db.session.add(muscle_group_obj)
                db.session.commit()

            # Create the MovementMuscleGroup relationship
            mmg = MovementMuscleGroup(
                movement_id=movement_obj.id,
                muscle_group_id=muscle_group_obj.id,
                impact=impact
            )
            db.session.add(mmg)

    db.session.commit()

    return redirect(url_for('view_workout', workout_id=workout.id))



@app.route('/delete_workout/<int:workout_id>', methods=['POST'])
def delete_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    db.session.delete(workout)
    db.session.commit()
    flash("Workout has been removed.", "success")
    return redirect(url_for('index'))  # Redirect to home or desired page


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

    # Get the time filter from the query parameter
    time_filter = request.args.get('time_filter', 'all')  # Default to 'all'

    # Get the current date
    current_date = datetime.now().date()

    # Determine the length of the period for the current and previous timeframes
    if time_filter == 'weekly':
        period_length = 7
    elif time_filter == 'monthly':
        period_length = 30
    else:  # 'all'
        period_length = 30  # For "all," we default to comparing the last 30 days vs the 30 days prior

    # Define the current and previous timeframes
    current_start_date = current_date - timedelta(days=period_length)
    previous_start_date = current_start_date - timedelta(days=period_length)

    # Get workouts for the current period
    current_workouts = Workout.query.filter(
        Workout.user_id == user_id,
        Workout.completion_date != None,
        Workout.completion_date >= current_start_date,
        Workout.completion_date < current_date
    ).all()

    # Get workouts for the previous period
    previous_workouts = Workout.query.filter(
        Workout.user_id == user_id,
        Workout.completion_date != None,
        Workout.completion_date >= previous_start_date,
        Workout.completion_date < current_start_date
    ).all()

    # Calculate muscle group workloads for the current and previous periods
    def calculate_workloads(workouts):
        workloads = {}
        for workout in workouts:
            for wm in workout.workout_movements:
                for mg in wm.movement.muscle_groups:
                    muscle_group_name = mg.muscle_group.name
                    volume = wm.sets * wm.reps_per_set * wm.weight * (mg.impact / 100)
                    workloads[muscle_group_name] = workloads.get(muscle_group_name, 0) + volume
        return workloads

    current_values = calculate_workloads(current_workouts)
    previous_values = calculate_workloads(previous_workouts)

    # Calculate percentage changes for muscle groups
    muscle_group_changes = []
    for muscle_group, current_value in current_values.items():
        previous_value = previous_values.get(muscle_group, 0)
        if previous_value > 0:
            change = ((current_value - previous_value) / previous_value) * 100
        else:
            change = 100.0 if current_value > 0 else 0.0
        muscle_group_changes.append((muscle_group, round(current_value, 2), round(change, 2)))

    # Sort by absolute percentage change and select the top 5
    top_changes = sorted(muscle_group_changes, key=lambda x: abs(x[2]), reverse=True)[:5]
    progress_data = {
        group: {
            'current_value': value,
            'change_percentage': change
        }
        for group, value, change in top_changes
    }

    print(f"Progress data (top 5 movements): {progress_data}")
    print(f"Muscle group changes: {muscle_group_changes}")

    return render_template(
        'stats.html',
        workouts=current_workouts,
        progress_data=progress_data,
        time_filter=time_filter
    )




if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

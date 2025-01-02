from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from models import db, Movement, Workout, WorkoutMovement, User
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

# Ensure database tables exist
with app.app_context():
    db.create_all()


@app.route('/start_workout', methods=['GET'])
def start_workout():
    # Show all workouts that are not completed
    workouts = Workout.query.filter(Workout.status != 'completed').all()
    return render_template('start_workout.html', workouts=workouts)


@app.route('/new_workout', methods=['POST'])
def new_workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    name = request.form.get('name')
    date_str = request.form.get('date')

    if not name or not date_str:
        return jsonify({'error': 'Invalid data submitted'}), 400

    workout_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    user_id = session['user_id']  # Get the logged-in user's ID

    new_workout = Workout(name=name, date=workout_date, status='planned', user_id=user_id)
    db.session.add(new_workout)
    db.session.commit()

    return jsonify({'workout_id': new_workout.id})


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

    return redirect(url_for('view_workout', workout_id=workout.id))


@app.route('/workout/<int:workout_id>', methods=['GET', 'POST'])
def view_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)

    if request.method == 'POST':
        # Update the workout date
        new_date_str = request.form.get('new_date')
        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            workout.date = new_date
            db.session.commit()
        except ValueError:
            return "Invalid date format. Please use YYYY-MM-DD.", 400

        return redirect(url_for('view_workout', workout_id=workout_id))

    # We'll also need all movements for the dropdown
    all_movements = Movement.query.all()
    return render_template('workout_details.html', workout=workout, all_movements=all_movements)


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
        new_workout_movement = WorkoutMovement(
            workout_id=workout_id,
            movement_id=movement_id,
            sets=sets,
            reps_per_set=reps,
            weight=weight,
        )
        db.session.add(new_workout_movement)

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
        # Your workout generation logic
        if 'user_id' not in session:
            return redirect(url_for('login'))

        # Collect user inputs
        sex = request.form.get('sex')
        weight = request.form.get('weight')
        gymexp = request.form.get('gymexp')
        target = request.form.get('target')

        # Generate the workout plan (your existing logic)
        try:
            chatgpt_text = generate_workout_plan(sex, weight, gymexp, target)
        except Exception as e:
            return f"Error generating workout plan: {str(e)}", 500

        print("ChatGPT Response:", chatgpt_text)

        # Parse the response and save the workout (your existing logic)
        try:
            # Extract JSON-like text from the response
            if chatgpt_text.startswith("```") and chatgpt_text.endswith("```"):
                chatgpt_text = chatgpt_text.strip("```").strip()
                if chatgpt_text.startswith("json"):
                    chatgpt_text = chatgpt_text[4:].strip()

            # Try finding JSON even with extraneous text
            chatgpt_text = chatgpt_text.split('```')[0].strip()  # Split and take only JSON
            workout_json = json.loads(chatgpt_text)
        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)
            print("Raw ChatGPT Response:", chatgpt_text)
            return "Failed to parse JSON from ChatGPT!", 400

        user_id = session['user_id']
        workout_name = workout_json.get("workout_name", "Unnamed Workout")
        movements = workout_json.get("movements", [])

        new_workout = Workout(
            name=workout_name,
            date=datetime.now().date(),
            status='planned',
            user_id=user_id
        )
        db.session.add(new_workout)
        db.session.commit()

        for m in movements:
            name = m.get("name", "Unknown Movement")
            sets = m.get("sets", 3)
            reps = m.get("reps", 10)
            weight = float(m.get("weight", 0.0))

            movement_obj = Movement.query.filter_by(name=name).first()
            if not movement_obj:
                movement_obj = Movement(name=name)
                db.session.add(movement_obj)
                db.session.commit()

            wm = WorkoutMovement(
                workout_id=new_workout.id,
                movement_id=movement_obj.id,
                sets=sets,
                reps_per_set=reps,
                weight=weight
            )
            db.session.add(wm)

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
    workout.completion_date = datetime.now().date()

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


@app.route('/stats', methods=['GET'])
def stats():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Get the time filter from the query parameter
    time_filter = request.args.get('time_filter', 'all')  # Default to 'all'

    # Get the current date
    current_date = datetime.now().date()

    # Filter workouts based on the time filter
    if time_filter == 'weekly':
        start_date = current_date - timedelta(days=current_date.weekday())  # Start of the week
        workouts = Workout.query.filter(
            Workout.user_id == user_id,
            Workout.completion_date != None,  # Exclude None completion_date
            Workout.completion_date >= start_date
        ).all()
    elif time_filter == 'monthly':
        start_date = current_date.replace(day=1)  # Start of the month
        workouts = Workout.query.filter(
            Workout.user_id == user_id,
            Workout.completion_date != None,  # Exclude None completion_date
            Workout.completion_date >= start_date
        ).all()
    else:
        workouts = Workout.query.filter(
            Workout.user_id == user_id,
            Workout.completion_date != None  # Exclude None completion_date
        ).all()

    # Track progress for movements
    movement_progress = {}
    for workout in workouts:
        for wm in workout.workout_movements:
            movement_name = wm.movement.name
            if movement_name not in movement_progress:
                movement_progress[movement_name] = []
            movement_progress[movement_name].append({
                'date': workout.completion_date,
                'sets': wm.sets,
                'reps': wm.reps_per_set,
                'weight': wm.weight
            })

    # Calculate progress
    progress_data = {}
    for movement, records in movement_progress.items():
        records = [r for r in records if r['date'] is not None]  # Exclude None dates
        records.sort(key=lambda x: x['date'])  # Sort by date
        if len(records) > 1:  # Only calculate progress if there is more than one record
            latest = records[-1]
            previous = records[-2]
            progress_data[movement] = {
                'sets': latest['sets'] - previous['sets'],
                'reps': latest['reps'] - previous['reps'],
                'weight': latest['weight'] - previous['weight']
            }

    return render_template(
        'stats.html',
        workouts=workouts,
        progress_data=progress_data,
        time_filter=time_filter
    )




if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

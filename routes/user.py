# user_routes.py

from flask import Blueprint, request, redirect, url_for, session, flash, jsonify
from models import User
from init_db import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

user_bp = Blueprint('user_bp', __name__)

def get_user_data(user_id):
    user = User.query.get(user_id)
    if not user:
        return None

    user_data = {
        "username": user.username,
        "workouts": []
    }

    # EXACT same code as original ...
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


@user_bp.route('/update_user', methods=['POST'])
def update_user():
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for('main_bp.index'))

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
    return redirect(url_for('main_bp.index'))


@user_bp.route('/user_data', methods=['GET'])
def user_data():
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    user_id = session['user_id']
    user = User.query.get_or_404(user_id)

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

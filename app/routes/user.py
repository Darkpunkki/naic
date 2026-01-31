# user_routes.py

from flask import Blueprint, request, redirect, url_for, session, flash, jsonify
from app.models import User
from scripts.init_db import db
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
        return redirect(url_for('auth.login'))

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

    workout_goal = request.form.get('workout_goal')
    if workout_goal:
        user.workout_goal = workout_goal

    db.session.commit()
    flash("Profile updated successfully!", "success")
    return redirect(url_for('main_bp.index'))


@user_bp.route('/user_data', methods=['GET'])
def user_data():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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


@user_bp.route('/delete_account', methods=['POST'])
def delete_account():
    """
    Permanently delete the user's account and all associated data.
    This includes: workouts, feedback profiles, group memberships, etc.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    user = User.query.get(user_id)

    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    try:
        # Delete the user - cascade relationships will handle associated data
        # (workouts, feedback profiles, group memberships, etc.)
        db.session.delete(user)
        db.session.commit()

        # Clear the session
        session.clear()

        return jsonify({'success': True, 'message': 'Account deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting account: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete account'}), 500

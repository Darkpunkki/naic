# leaderboard_routes.py

from flask import Blueprint, render_template, session
from datetime import datetime, timedelta
from sqlalchemy import func

from init_db import db
from models import User, Workout

leaderboard_bp = Blueprint('leaderboard_bp', __name__)

@leaderboard_bp.route('/leaderboard')
def leaderboard():
    # EXACT code from original:
    start_of_week = datetime.now() - timedelta(days=7)

    user_workout_counts = (
        db.session.query(
            User.username,
            func.count(Workout.workout_id).label('workout_count')
        )
        .join(Workout, Workout.user_id == User.user_id)
        .filter(Workout.workout_date >= start_of_week)
        .group_by(User.username)
        .order_by(func.count(Workout.workout_id).desc())
        .all()
    )

    return render_template('leaderboard.html', user_workout_counts=user_workout_counts, enumerate=enumerate)

# main_routes.py

from flask import Blueprint, render_template, session, redirect, url_for
from app.models import User

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    return render_template('index.html', username=session['username'], user=user)

# main_routes.py

from flask import Blueprint, render_template, session, redirect, url_for
from models import User

main_bp = Blueprint('main_bp', __name__)

# main.py
@main_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    # Groups the current user is in (accepted membership)
    my_groups = []
    if user:
        my_groups = [
            mem.group
            for mem in user.user_groups
            if mem.membership_status == 'accepted'
        ]

    # Pending invitations for the current user
    pending_invitations = [
        mem for mem in user.user_groups
        if mem.membership_status == 'pending'
    ]

    return render_template(
        'index.html',
        username=session['username'],
        user=user,
        my_groups=my_groups,
        pending_invitations=pending_invitations
    )


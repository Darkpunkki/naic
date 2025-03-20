# groups.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, UserGroup, UserGroupMembership, User
from datetime import datetime

groups_bp = Blueprint('groups_bp', __name__)

@groups_bp.route('/groups/create_group', methods=['POST'])
def create_group():
    """
    Creates a new user group with the current user as a member.
    """
    if 'user_id' not in session:
        flash("You must be logged in to create a group.", "error")
        return redirect(url_for('auth_bp.login'))

    group_name = request.form.get('group_name')
    group_description = request.form.get('group_description', '')

    if not group_name:
        flash("Group name is required.", "error")
        return redirect(url_for('main_bp.index'))

    # Create the group
    new_group = UserGroup(
        group_name=group_name.strip(),
        group_description=group_description.strip()
    )
    db.session.add(new_group)
    db.session.commit()

    # Automatically add the current user as an "accepted" member
    membership = UserGroupMembership(
        user_id=session['user_id'],
        group_id=new_group.group_id,
        joined_at=datetime.now(),
        membership_status='accepted'  # We'll add this column in the model
    )
    db.session.add(membership)
    db.session.commit()

    flash(f"Group '{group_name}' created successfully!", "success")
    return redirect(url_for('main_bp.index'))


@groups_bp.route('/groups/invite_user', methods=['POST'])
def invite_user():
    """
    Invites a user (by username) to join one of the current user's groups.
    """
    if 'user_id' not in session:
        flash("You must be logged in to invite users.", "error")
        return redirect(url_for('auth_bp.login'))

    group_id = request.form.get('group_id')
    username = request.form.get('username')

    if not group_id or not username:
        flash("Must specify both group and username to invite.", "error")
        return redirect(url_for('main_bp.index'))

    # Check that the group belongs to the current user (i.e., current user is a member of that group).
    existing_membership = UserGroupMembership.query.filter_by(
        user_id=session['user_id'],
        group_id=group_id,
        membership_status='accepted'
    ).first()

    if not existing_membership:
        flash("You do not belong to that group or it doesn't exist.", "error")
        return redirect(url_for('main_bp.index'))

    # Find the user we want to invite
    invitee = User.query.filter_by(username=username).first()
    if not invitee:
        flash("No user found with that username.", "error")
        return redirect(url_for('main_bp.index'))

    # Check if the user is already in the group
    existing_invite = UserGroupMembership.query.filter_by(
        user_id=invitee.user_id,
        group_id=group_id
    ).first()

    if existing_invite:
        if existing_invite.membership_status == 'accepted':
            flash("That user is already a member of this group.", "info")
        elif existing_invite.membership_status == 'pending':
            flash("That user has already been invited and not responded yet.", "info")
        else:
            # Possibly they previously declined, so we can re-invite
            existing_invite.membership_status = 'pending'
            existing_invite.joined_at = datetime.now()
            db.session.commit()
            flash("User has been reinvited to the group.", "success")
        return redirect(url_for('main_bp.index'))

    # Otherwise, create a new pending membership
    new_membership = UserGroupMembership(
        user_id=invitee.user_id,
        group_id=int(group_id),
        joined_at=datetime.now(),
        membership_status='pending'
    )
    db.session.add(new_membership)
    db.session.commit()

    flash("Invitation sent!", "success")
    return redirect(url_for('main_bp.index'))


@groups_bp.route('/groups/accept_invite', methods=['POST'])
def accept_invite():
    """
    Accept the invitation to join a group.
    membership_id is posted from the form.
    """
    if 'user_id' not in session:
        flash("You must be logged in to accept invitations.", "error")
        return redirect(url_for('auth_bp.login'))

    membership_id = request.form.get('membership_id')
    membership = UserGroupMembership.query.get_or_404(membership_id)

    # Ensure that the membership belongs to the current user
    if membership.user_id != session['user_id']:
        flash("You cannot accept an invite that isn't yours.", "error")
        return redirect(url_for('main_bp.index'))

    membership.membership_status = 'accepted'
    membership.joined_at = datetime.now()
    db.session.commit()

    flash(f"You have joined the group '{membership.group.group_name}'!", "success")
    return redirect(url_for('main_bp.index'))


@groups_bp.route('/groups/decline_invite', methods=['POST'])
def decline_invite():
    """
    Decline the invitation to join a group.
    membership_id is posted from the form.
    """
    if 'user_id' not in session:
        flash("You must be logged in to decline invitations.", "error")
        return redirect(url_for('auth_bp.login'))

    membership_id = request.form.get('membership_id')
    membership = UserGroupMembership.query.get_or_404(membership_id)

    if membership.user_id != session['user_id']:
        flash("You cannot decline an invite that isn't yours.", "error")
        return redirect(url_for('main_bp.index'))

    membership.membership_status = 'declined'
    db.session.commit()

    flash(f"You declined the invitation to join '{membership.group.group_name}'.", "info")
    return redirect(url_for('main_bp.index'))

# groups.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from datetime import datetime
from app.models import (
    db,
    User,
    UserGroup,
    UserGroupMembership,
    GroupInvitation,
    GroupJoinRequest,
    WorkoutComment,
)
from sqlalchemy import or_
from app.services.group_access_service import GroupAccessService
from app.services.group_workout_service import GroupWorkoutService
from app.services.workout_comment_service import WorkoutCommentService

groups_bp = Blueprint('groups', __name__, url_prefix='/groups')


def get_current_user():
    """Helper to get the current logged-in user."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


def _parse_bool_filter(raw_value):
    if raw_value is None:
        return None
    value = str(raw_value).strip().lower()
    if value in {'true', '1', 'yes', 'completed'}:
        return True
    if value in {'false', '0', 'no', 'incomplete'}:
        return False
    return None


def _parse_date_filter(raw_value):
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _set_last_group_feed_group(group_id):
    session['last_group_feed_group_id'] = int(group_id)


def _abbreviate_number(value):
    number = float(value or 0.0)
    absolute = abs(number)
    suffix = ''
    scaled = number

    if absolute >= 1_000_000_000:
        scaled = number / 1_000_000_000
        suffix = 'b'
    elif absolute >= 1_000_000:
        scaled = number / 1_000_000
        suffix = 'm'
    elif absolute >= 1_000:
        scaled = number / 1_000
        suffix = 'k'

    if abs(scaled) >= 100:
        text = f"{scaled:.0f}"
    elif abs(scaled) >= 10:
        text = f"{scaled:.1f}"
    else:
        text = f"{scaled:.2f}"

    text = text.rstrip('0').rstrip('.')
    return f"{text}{suffix}"


def _muscle_color(label):
    hash_value = 0
    for char in label:
        hash_value = ord(char) + ((hash_value << 5) - hash_value)
    hue = abs(hash_value) % 360
    return f"hsl({hue}, 70%, 55%)"


def _calculate_workout_feed_metrics(workout):
    """Calculate per-workout feed metrics (points and lifted load)."""
    total_kg_lifted = 0.0
    points_by_muscle = {}

    for workout_movement in workout.workout_movements:
        impacts = workout_movement.calculate_muscle_group_impact() or {}
        for muscle_name, impact_value in impacts.items():
            points_by_muscle[muscle_name] = points_by_muscle.get(muscle_name, 0.0) + float(impact_value or 0.0)

        for single_set in workout_movement.sets:
            if single_set.entries:
                for entry in single_set.entries:
                    reps = float(entry.reps or 0.0)
                    weight_value = float(entry.weight_value or 0.0)
                    total_kg_lifted += reps * weight_value
                continue

            rep_values = [float(rep.rep_count or 0.0) for rep in (single_set.reps or [])]
            weight_values = [float(weight.weight_value or 0.0) for weight in (single_set.weights or [])]

            if not rep_values or not weight_values:
                continue

            if len(rep_values) == len(weight_values):
                for index, rep_value in enumerate(rep_values):
                    total_kg_lifted += rep_value * weight_values[index]
            elif len(weight_values) == 1:
                for rep_value in rep_values:
                    total_kg_lifted += rep_value * weight_values[0]
            elif len(rep_values) == 1:
                for weight_value in weight_values:
                    total_kg_lifted += rep_values[0] * weight_value
            else:
                total_kg_lifted += rep_values[0] * weight_values[0]

    points_breakdown = sorted(points_by_muscle.items(), key=lambda item: item[1], reverse=True)
    total_points = sum(points_by_muscle.values())

    graph_segments = []
    for muscle_name, points in points_breakdown[:4]:
        ratio_pct = (float(points) / total_points * 100.0) if total_points > 0 else 0.0
        graph_segments.append({
            'muscle_name': muscle_name,
            'points': round(float(points), 2),
            'points_label': _abbreviate_number(points),
            'ratio_pct': ratio_pct,
            'color': _muscle_color(muscle_name),
        })

    if len(points_breakdown) > 4:
        other_points = sum(float(points) for _, points in points_breakdown[4:])
        ratio_pct = (other_points / total_points * 100.0) if total_points > 0 else 0.0
        graph_segments.append({
            'muscle_name': 'Other',
            'points': round(other_points, 2),
            'points_label': _abbreviate_number(other_points),
            'ratio_pct': ratio_pct,
            'color': 'rgba(148, 163, 184, 0.95)',
        })

    return {
        'total_kg_lifted': round(total_kg_lifted, 2),
        'total_points': round(total_points, 2),
        'total_kg_lifted_label': _abbreviate_number(total_kg_lifted),
        'total_points_label': _abbreviate_number(total_points),
        'points_breakdown': points_breakdown,
        'graph_segments': graph_segments,
    }


@groups_bp.route('/create', methods=['POST'])
def create_group():
    """Create a new group. Creator becomes owner."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    group_name = data.get('group_name', '').strip()
    group_description = data.get('group_description', '').strip()

    if not group_name:
        return jsonify({'error': 'Group name is required'}), 400

    # Create the group
    new_group = UserGroup(
        group_name=group_name,
        group_description=group_description
    )
    db.session.add(new_group)
    db.session.flush()  # Get the group_id

    # Add creator as owner
    membership = UserGroupMembership(
        user_id=user.user_id,
        group_id=new_group.group_id,
        role='owner'
    )
    db.session.add(membership)
    db.session.commit()
    _set_last_group_feed_group(new_group.group_id)

    return jsonify({
        'success': True,
        'group': {
            'group_id': new_group.group_id,
            'group_name': new_group.group_name,
            'group_description': new_group.group_description,
            'role': 'owner',
            'member_count': 1
        }
    }), 201


@groups_bp.route('/my-groups', methods=['GET'])
def get_my_groups():
    """List all groups the current user is a member of."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    memberships = UserGroupMembership.query.filter_by(user_id=user.user_id).all()

    groups = []
    for m in memberships:
        member_count = UserGroupMembership.query.filter_by(group_id=m.group_id).count()
        groups.append({
            'group_id': m.group.group_id,
            'group_name': m.group.group_name,
            'group_description': m.group.group_description,
            'role': m.role,
            'member_count': member_count,
            'joined_at': m.joined_at.isoformat() if m.joined_at else None
        })

    return jsonify({'groups': groups})


@groups_bp.route('/<int:group_id>/leave', methods=['POST'])
def leave_group(group_id):
    """Leave a group. Owner must transfer ownership or delete if last member."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    membership = UserGroupMembership.query.filter_by(
        user_id=user.user_id,
        group_id=group_id
    ).first()

    if not membership:
        return jsonify({'error': 'You are not a member of this group'}), 404

    # Count members
    member_count = UserGroupMembership.query.filter_by(group_id=group_id).count()

    if membership.role == 'owner':
        if member_count > 1:
            # Owner must transfer ownership first
            return jsonify({
                'error': 'You are the owner. Transfer ownership to another member or delete the group first.'
            }), 400
        else:
            # Last member, delete the group entirely
            # Delete all invitations for this group
            GroupInvitation.query.filter_by(group_id=group_id).delete()
            # Delete the membership
            db.session.delete(membership)
            # Delete the group
            group = UserGroup.query.get(group_id)
            if group:
                db.session.delete(group)
            db.session.commit()
            if session.get('last_group_feed_group_id') == group_id:
                session.pop('last_group_feed_group_id', None)
            return jsonify({'success': True, 'message': 'Group deleted as you were the last member'})

    # Regular member or admin can just leave
    db.session.delete(membership)
    db.session.commit()
    if session.get('last_group_feed_group_id') == group_id:
        session.pop('last_group_feed_group_id', None)

    return jsonify({'success': True, 'message': 'You have left the group'})


@groups_bp.route('/<int:group_id>/invite', methods=['POST'])
def invite_user(group_id):
    """Invite a user to the group by username."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    # Check if current user is a member of the group
    membership = UserGroupMembership.query.filter_by(
        user_id=user.user_id,
        group_id=group_id
    ).first()

    if not membership:
        return jsonify({'error': 'You are not a member of this group'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    if not username:
        return jsonify({'error': 'Username is required'}), 400

    # Find the user to invite
    invitee = User.query.filter_by(username=username).first()
    if not invitee:
        return jsonify({'error': 'User not found'}), 404

    # Check if already a member
    existing_membership = UserGroupMembership.query.filter_by(
        user_id=invitee.user_id,
        group_id=group_id
    ).first()
    if existing_membership:
        return jsonify({'error': 'User is already a member of this group'}), 400

    # Check for existing pending invitation
    existing_invitation = GroupInvitation.query.filter_by(
        group_id=group_id,
        invitee_user_id=invitee.user_id,
        status='pending'
    ).first()
    if existing_invitation:
        return jsonify({'error': 'User already has a pending invitation'}), 400

    # Create the invitation
    invitation = GroupInvitation(
        group_id=group_id,
        inviter_user_id=user.user_id,
        invitee_user_id=invitee.user_id,
        status='pending'
    )
    db.session.add(invitation)
    db.session.commit()

    group = UserGroup.query.get(group_id)
    return jsonify({
        'success': True,
        'message': f'Invitation sent to {username}',
        'invitation': {
            'invitation_id': invitation.invitation_id,
            'group_name': group.group_name,
            'invitee_username': invitee.username
        }
    })


@groups_bp.route('/invitations', methods=['GET'])
def get_invitations():
    """Get pending invitations for the current user."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    invitations = GroupInvitation.query.filter_by(
        invitee_user_id=user.user_id,
        status='pending'
    ).all()

    result = []
    for inv in invitations:
        result.append({
            'invitation_id': inv.invitation_id,
            'group_id': inv.group_id,
            'group_name': inv.group.group_name,
            'group_description': inv.group.group_description,
            'inviter_username': inv.inviter_account.username,
            'created_at': inv.created_at.isoformat() if inv.created_at else None
        })

    return jsonify({'invitations': result})


@groups_bp.route('/invitations/<int:invitation_id>/accept', methods=['POST'])
def accept_invitation(invitation_id):
    """Accept an invitation to join a group."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    invitation = GroupInvitation.query.get(invitation_id)
    if not invitation:
        return jsonify({'error': 'Invitation not found'}), 404

    if invitation.invitee_user_id != user.user_id:
        return jsonify({'error': 'This invitation is not for you'}), 403

    if invitation.status != 'pending':
        return jsonify({'error': 'Invitation has already been responded to'}), 400

    # Update invitation status
    invitation.status = 'accepted'
    invitation.responded_at = datetime.utcnow()

    # Create membership
    membership = UserGroupMembership(
        user_id=user.user_id,
        group_id=invitation.group_id,
        role='member'
    )
    db.session.add(membership)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'You have joined {invitation.group.group_name}',
        'group': {
            'group_id': invitation.group_id,
            'group_name': invitation.group.group_name
        }
    })


@groups_bp.route('/invitations/<int:invitation_id>/decline', methods=['POST'])
def decline_invitation(invitation_id):
    """Decline an invitation to join a group."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    invitation = GroupInvitation.query.get(invitation_id)
    if not invitation:
        return jsonify({'error': 'Invitation not found'}), 404

    if invitation.invitee_user_id != user.user_id:
        return jsonify({'error': 'This invitation is not for you'}), 403

    if invitation.status != 'pending':
        return jsonify({'error': 'Invitation has already been responded to'}), 400

    # Update invitation status
    invitation.status = 'declined'
    invitation.responded_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Invitation declined'
    })


# ==========================================
# GROUP BROWSING & JOIN REQUESTS
# ==========================================

@groups_bp.route('/feed', methods=['GET'])
def open_group_feed():
    """Open the feed for a selected group, or fallback to the last selected group."""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    memberships = (
        UserGroupMembership.query
        .filter_by(user_id=user.user_id)
        .order_by(UserGroupMembership.joined_at.asc())
        .all()
    )
    if not memberships:
        flash('Join a group first to view a group feed.', 'error')
        return redirect(url_for('groups.browse_groups'))

    member_group_ids = [membership.group_id for membership in memberships]
    requested_group_id = request.args.get('group_id', type=int)
    target_group_id = None

    if requested_group_id:
        if requested_group_id in member_group_ids:
            target_group_id = requested_group_id
        else:
            flash('That group is not available in your memberships.', 'error')

    if target_group_id is None:
        saved_group_id = session.get('last_group_feed_group_id')
        if saved_group_id in member_group_ids:
            target_group_id = saved_group_id

    if target_group_id is None:
        target_group_id = member_group_ids[0]

    _set_last_group_feed_group(target_group_id)
    return redirect(url_for('groups.group_workouts', group_id=target_group_id))


@groups_bp.route('/browse', methods=['GET'])
def browse_groups():
    """Browse all available groups with optional search."""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    search_query = request.args.get('search', '').strip()

    # Get all groups
    query = UserGroup.query

    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                UserGroup.group_name.ilike(f'%{search_query}%'),
                UserGroup.group_description.ilike(f'%{search_query}%')
            )
        )

    all_groups = query.order_by(UserGroup.created_at.desc()).all()

    # Get user's current groups and roles
    user_memberships = UserGroupMembership.query.filter_by(user_id=user.user_id).all()
    user_memberships_by_group_id = {m.group_id: m for m in user_memberships}
    user_group_ids = set(user_memberships_by_group_id.keys())

    # Get pending requests
    pending_request_group_ids = [
        r.group_id for r in GroupJoinRequest.query.filter_by(user_id=user.user_id, status='pending').all()
    ]

    # Build group list with metadata
    groups = []
    for group in all_groups:
        member_count = UserGroupMembership.query.filter_by(group_id=group.group_id).count()

        # Determine user's relationship to this group
        if group.group_id in user_group_ids:
            status = 'member'
        elif group.group_id in pending_request_group_ids:
            status = 'pending'
        else:
            status = 'not_member'

        groups.append({
            'group': group,
            'member_count': member_count,
            'status': status,
            'role': user_memberships_by_group_id[group.group_id].role if group.group_id in user_group_ids else None,
        })

    return render_template('browse_groups.html', groups=groups, search_query=search_query)


@groups_bp.route('/<int:group_id>/request', methods=['POST'])
def request_join(group_id):
    """Request to join a group."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    # Check if group exists
    group = UserGroup.query.get(group_id)
    if not group:
        return jsonify({'error': 'Group not found'}), 404

    # Check if already a member
    existing_membership = UserGroupMembership.query.filter_by(
        user_id=user.user_id,
        group_id=group_id
    ).first()
    if existing_membership:
        return jsonify({'error': 'You are already a member'}), 400

    # Check for existing pending request
    existing_request = GroupJoinRequest.query.filter_by(
        user_id=user.user_id,
        group_id=group_id,
        status='pending'
    ).first()
    if existing_request:
        return jsonify({'error': 'You already have a pending request'}), 400

    # Create join request
    join_request = GroupJoinRequest(
        user_id=user.user_id,
        group_id=group_id,
        status='pending'
    )
    db.session.add(join_request)
    db.session.commit()

    flash(f'Join request sent to {group.group_name}', 'success')
    return jsonify({'success': True, 'message': f'Request sent to {group.group_name}'})


@groups_bp.route('/<int:group_id>/manage', methods=['GET'])
def manage_group(group_id):
    """Group management page (for owners/admins)."""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    # Check if user is owner or admin
    membership = UserGroupMembership.query.filter_by(
        user_id=user.user_id,
        group_id=group_id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        flash('You do not have permission to manage this group', 'error')
        return redirect(url_for('groups.browse_groups'))

    group = UserGroup.query.get_or_404(group_id)

    # Get all members
    members = []
    memberships = UserGroupMembership.query.filter_by(group_id=group_id).all()
    for m in memberships:
        members.append({
            'user': m.user_account,
            'role': m.role,
            'joined_at': m.joined_at,
            'membership_id': m.membership_id
        })

    # Get pending join requests
    pending_requests = []
    requests = GroupJoinRequest.query.filter_by(group_id=group_id, status='pending').all()
    for r in requests:
        pending_requests.append({
            'request_id': r.request_id,
            'user': r.requester_account,
            'created_at': r.created_at
        })

    return render_template(
        'manage_group.html',
        group=group,
        members=members,
        pending_requests=pending_requests,
        user_role=membership.role
    )


@groups_bp.route('/<int:group_id>/requests/<int:request_id>/accept', methods=['POST'])
def accept_join_request(group_id, request_id):
    """Accept a join request (owner/admin only)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    # Check permissions
    membership = UserGroupMembership.query.filter_by(
        user_id=user.user_id,
        group_id=group_id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        return jsonify({'error': 'Permission denied'}), 403

    # Get the request
    join_request = GroupJoinRequest.query.get(request_id)
    if not join_request or join_request.group_id != group_id:
        return jsonify({'error': 'Request not found'}), 404

    if join_request.status != 'pending':
        return jsonify({'error': 'Request already processed'}), 400

    # Update request
    join_request.status = 'accepted'
    join_request.responded_at = datetime.utcnow()
    join_request.responded_by = user.user_id

    # Create membership
    new_membership = UserGroupMembership(
        user_id=join_request.user_id,
        group_id=group_id,
        role='member'
    )
    db.session.add(new_membership)
    db.session.commit()

    flash(f'{join_request.requester_account.username} has been added to the group', 'success')
    return jsonify({'success': True})


@groups_bp.route('/<int:group_id>/requests/<int:request_id>/reject', methods=['POST'])
def reject_join_request(group_id, request_id):
    """Reject a join request (owner/admin only)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    # Check permissions
    membership = UserGroupMembership.query.filter_by(
        user_id=user.user_id,
        group_id=group_id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        return jsonify({'error': 'Permission denied'}), 403

    # Get the request
    join_request = GroupJoinRequest.query.get(request_id)
    if not join_request or join_request.group_id != group_id:
        return jsonify({'error': 'Request not found'}), 404

    if join_request.status != 'pending':
        return jsonify({'error': 'Request already processed'}), 400

    # Update request
    join_request.status = 'rejected'
    join_request.responded_at = datetime.utcnow()
    join_request.responded_by = user.user_id
    db.session.commit()

    flash('Join request rejected', 'success')
    return jsonify({'success': True})


@groups_bp.route('/<int:group_id>/members/<int:member_user_id>/kick', methods=['POST'])
def kick_member(group_id, member_user_id):
    """Kick a member from the group (owner/admin only)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    # Check permissions
    membership = UserGroupMembership.query.filter_by(
        user_id=user.user_id,
        group_id=group_id
    ).first()

    if not membership or membership.role not in ['owner', 'admin']:
        return jsonify({'error': 'Permission denied'}), 403

    # Get member to kick
    member_membership = UserGroupMembership.query.filter_by(
        user_id=member_user_id,
        group_id=group_id
    ).first()

    if not member_membership:
        return jsonify({'error': 'Member not found'}), 404

    # Can't kick yourself
    if member_user_id == user.user_id:
        return jsonify({'error': 'You cannot kick yourself'}), 400

    # Only owner can kick admins or other owners
    if member_membership.role in ['owner', 'admin'] and membership.role != 'owner':
        return jsonify({'error': 'Only the owner can remove admins or owners'}), 403

    # Can't kick the last owner
    if member_membership.role == 'owner':
        owner_count = UserGroupMembership.query.filter_by(group_id=group_id, role='owner').count()
        if owner_count <= 1:
            return jsonify({'error': 'Cannot remove the last owner'}), 400

    # Remove member
    kicked_username = member_membership.user_account.username
    db.session.delete(member_membership)
    db.session.commit()

    flash(f'{kicked_username} has been removed from the group', 'success')
    return jsonify({'success': True})


# ==========================================
# GROUP WORKOUTS + COMMENTS
# ==========================================

@groups_bp.route('/<int:group_id>/workouts', methods=['GET'])
def group_workouts(group_id):
    """Browse workouts from all members in a group."""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    group = UserGroup.query.get_or_404(group_id)
    membership = GroupAccessService.get_membership(user.user_id, group_id)
    if not membership:
        flash('You are not a member of this group', 'error')
        return redirect(url_for('groups.browse_groups')), 403
    _set_last_group_feed_group(group_id)

    page = request.args.get('page', default=1, type=int)
    page_size = request.args.get('page_size', default=15, type=int)
    member_user_id = request.args.get('member', type=int)
    completed = True
    start_date = _parse_date_filter(request.args.get('start') or request.args.get('from'))
    end_date = _parse_date_filter(request.args.get('end') or request.args.get('to'))

    try:
        payload = GroupWorkoutService.list_group_workouts(
            group_id=group_id,
            viewer_user_id=user.user_id,
            page=page,
            page_size=page_size,
            member_user_id=member_user_id,
            completed=completed,
            start_date=start_date,
            end_date=end_date,
        )
    except PermissionError:
        flash('You are not allowed to view workouts for this group', 'error')
        return redirect(url_for('groups.browse_groups')), 403

    members = (
        User.query.join(UserGroupMembership, UserGroupMembership.user_id == User.user_id)
        .filter(UserGroupMembership.group_id == group_id)
        .order_by(User.username.asc())
        .all()
    )
    viewer_groups = (
        UserGroupMembership.query
        .join(UserGroup, UserGroup.group_id == UserGroupMembership.group_id)
        .filter(UserGroupMembership.user_id == user.user_id)
        .order_by(UserGroup.group_name.asc())
        .all()
    )
    workout_feed_metrics = {
        workout.workout_id: _calculate_workout_feed_metrics(workout)
        for workout in payload['workouts']
    }

    return render_template(
        'group_workouts.html',
        group=group,
        workouts=payload['workouts'],
        workout_feed_metrics=workout_feed_metrics,
        members=members,
        viewer_groups=viewer_groups,
        total=payload['total'],
        page=payload['page'],
        page_size=payload['page_size'],
        total_pages=payload['total_pages'],
        selected_member=member_user_id,
        selected_group_id=group_id,
        selected_from=request.args.get('start', request.args.get('from', '')),
        selected_to=request.args.get('end', request.args.get('to', '')),
        can_manage_group=membership.role in ('owner', 'admin'),
    )


@groups_bp.route('/<int:group_id>/workouts/<int:workout_id>', methods=['GET'])
def view_group_workout(group_id, workout_id):
    """Read-only workout detail for a workout visible to this group."""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    group = UserGroup.query.get_or_404(group_id)
    membership = GroupAccessService.get_membership(user.user_id, group_id)
    if not membership:
        flash('You are not a member of this group', 'error')
        return redirect(url_for('groups.browse_groups')), 403
    _set_last_group_feed_group(group_id)

    try:
        workout = GroupWorkoutService.get_group_workout(group_id, workout_id, user.user_id)
    except LookupError:
        flash('Workout not found', 'error')
        return redirect(url_for('groups.group_workouts', group_id=group_id)), 404
    except PermissionError:
        flash('Workout is not visible in this group', 'error')
        return redirect(url_for('groups.group_workouts', group_id=group_id)), 403

    muscle_group_impacts = None
    if workout.is_completed:
        aggregate_impacts = {}
        for workout_movement in workout.workout_movements:
            for mg_name, impact_value in workout_movement.calculate_muscle_group_impact().items():
                aggregate_impacts[mg_name] = aggregate_impacts.get(mg_name, 0) + impact_value
        muscle_group_impacts = sorted(aggregate_impacts.items(), key=lambda item: item[1], reverse=True)

    comments = WorkoutCommentService.list_comments(group_id, workout_id)
    can_moderate = GroupAccessService.is_owner_or_admin(user.user_id, group_id)
    serialized_comments = [
        WorkoutCommentService.serialize_comment(comment, user.user_id, can_moderate)
        for comment in comments
    ]

    return render_template(
        'group_workout_detail.html',
        group=group,
        workout=workout,
        muscle_group_impacts=muscle_group_impacts,
        comments=serialized_comments,
        can_moderate=can_moderate,
        current_user_id=user.user_id,
    )


def _resolve_group_workout_for_api(group_id, workout_id):
    user = get_current_user()
    if not user:
        return None, None, jsonify({'error': 'Not authenticated'}), 401

    try:
        workout = GroupWorkoutService.get_group_workout(group_id, workout_id, user.user_id)
    except LookupError:
        return None, None, jsonify({'error': 'Workout not found'}), 404
    except PermissionError:
        return None, None, jsonify({'error': 'Forbidden'}), 403

    _set_last_group_feed_group(group_id)
    return user, workout, None, None


@groups_bp.route('/<int:group_id>/workouts/<int:workout_id>/comments', methods=['GET', 'POST'])
def workout_comments(group_id, workout_id):
    user, workout, error_response, status_code = _resolve_group_workout_for_api(group_id, workout_id)
    if error_response:
        return error_response, status_code

    can_moderate = GroupAccessService.is_owner_or_admin(user.user_id, group_id)

    if request.method == 'GET':
        comments = WorkoutCommentService.list_comments(group_id, workout.workout_id)
        serialized = [
            WorkoutCommentService.serialize_comment(comment, user.user_id, can_moderate)
            for comment in comments
        ]
        return jsonify({'comments': serialized})

    payload = request.get_json(silent=True) or {}
    body = payload.get('body', '')

    try:
        comment = WorkoutCommentService.create_comment(
            group_id=group_id,
            workout_id=workout.workout_id,
            author_user_id=user.user_id,
            body=body,
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    return jsonify({
        'success': True,
        'comment': WorkoutCommentService.serialize_comment(comment, user.user_id, can_moderate),
    }), 201


@groups_bp.route('/<int:group_id>/workouts/<int:workout_id>/comments/<int:comment_id>', methods=['PATCH'])
def update_workout_comment(group_id, workout_id, comment_id):
    user, workout, error_response, status_code = _resolve_group_workout_for_api(group_id, workout_id)
    if error_response:
        return error_response, status_code

    comment = WorkoutComment.query.filter_by(
        comment_id=comment_id,
        group_id=group_id,
        workout_id=workout.workout_id,
    ).first()
    if not comment:
        return jsonify({'error': 'Comment not found'}), 404

    if comment.author_user_id != user.user_id:
        return jsonify({'error': 'You can only edit your own comments'}), 403

    payload = request.get_json(silent=True) or {}
    body = payload.get('body', '')
    try:
        updated_comment = WorkoutCommentService.update_comment(comment, body)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    can_moderate = GroupAccessService.is_owner_or_admin(user.user_id, group_id)
    return jsonify({
        'success': True,
        'comment': WorkoutCommentService.serialize_comment(updated_comment, user.user_id, can_moderate),
    })


@groups_bp.route('/<int:group_id>/workouts/<int:workout_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_workout_comment(group_id, workout_id, comment_id):
    user, workout, error_response, status_code = _resolve_group_workout_for_api(group_id, workout_id)
    if error_response:
        return error_response, status_code

    comment = WorkoutComment.query.filter_by(
        comment_id=comment_id,
        group_id=group_id,
        workout_id=workout.workout_id,
    ).first()
    if not comment:
        return jsonify({'error': 'Comment not found'}), 404

    can_moderate = GroupAccessService.is_owner_or_admin(user.user_id, group_id)
    is_author = comment.author_user_id == user.user_id
    if not is_author and not can_moderate:
        return jsonify({'error': 'You do not have permission to delete this comment'}), 403

    deleted_comment = WorkoutCommentService.soft_delete_comment(comment)
    return jsonify({
        'success': True,
        'comment': WorkoutCommentService.serialize_comment(deleted_comment, user.user_id, can_moderate),
    })

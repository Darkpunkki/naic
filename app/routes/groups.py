# groups.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from datetime import datetime
from app.models import db, User, UserGroup, UserGroupMembership, GroupInvitation, GroupJoinRequest
from sqlalchemy import or_

groups_bp = Blueprint('groups', __name__, url_prefix='/groups')


def get_current_user():
    """Helper to get the current logged-in user."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


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
            return jsonify({'success': True, 'message': 'Group deleted as you were the last member'})

    # Regular member or admin can just leave
    db.session.delete(membership)
    db.session.commit()

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
            'inviter_username': inv.inviter.username,
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

    # Get user's current groups
    user_group_ids = [m.group_id for m in UserGroupMembership.query.filter_by(user_id=user.user_id).all()]

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
            'status': status
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
            'user': m.user,
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
            'user': r.user,
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

    flash(f'{join_request.user.username} has been added to the group', 'success')
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
    kicked_username = member_membership.user.username
    db.session.delete(member_membership)
    db.session.commit()

    flash(f'{kicked_username} has been removed from the group', 'success')
    return jsonify({'success': True})

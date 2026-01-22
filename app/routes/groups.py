# groups.py
from flask import Blueprint, request, jsonify, session
from datetime import datetime
from app.models import db, User, UserGroup, UserGroupMembership, GroupInvitation

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

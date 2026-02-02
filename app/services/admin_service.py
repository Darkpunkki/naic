"""
Admin Service - Business logic for admin operations.
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import or_

from app.models import (
    db, User, UserGroup, UserGroupMembership, Workout, AdminAuditLog,
    GroupInvitation, GroupJoinRequest
)


class AdminService:
    """Service class for admin operations on users and groups."""

    @staticmethod
    def get_all_users(page: int = 1, per_page: int = 20, search: Optional[str] = None):
        """
        Get paginated list of all users with optional search.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            search: Optional search term for username or email

        Returns:
            Pagination object with users
        """
        query = User.query

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term)
                )
            )

        return query.order_by(User.user_id).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @staticmethod
    def get_user_details(user_id: int):
        """
        Get detailed user info including workouts, groups, and stats.

        Args:
            user_id: The user's ID

        Returns:
            dict with user details or None if not found
        """
        user = User.query.get(user_id)
        if not user:
            return None

        # Get user's groups
        memberships = UserGroupMembership.query.filter_by(user_id=user_id).all()
        groups = []
        for m in memberships:
            group = UserGroup.query.get(m.group_id)
            if group:
                groups.append({
                    'group_id': group.group_id,
                    'group_name': group.group_name,
                    'role': m.role,
                    'joined_at': m.joined_at
                })

        # Get workout stats
        total_workouts = Workout.query.filter_by(user_id=user_id).count()
        completed_workouts = Workout.query.filter_by(user_id=user_id, is_completed=True).count()

        return {
            'user': user,
            'groups': groups,
            'total_workouts': total_workouts,
            'completed_workouts': completed_workouts
        }

    @staticmethod
    def update_user(admin_id: int, user_id: int, data: dict) -> tuple[bool, str]:
        """
        Update user fields and log the action.

        Args:
            admin_id: The admin performing the action
            user_id: The user to update
            data: Dict with fields to update (username, email, first_name, last_name, etc.)

        Returns:
            Tuple of (success, message)
        """
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"

        # Store original values for audit log
        original_values = {}
        updated_values = {}

        # Allowed fields for admin to update
        allowed_fields = [
            'username', 'email', 'first_name', 'last_name',
            'sex', 'bodyweight', 'gym_experience', 'workout_goal'
        ]

        for field in allowed_fields:
            if field in data:
                original_value = getattr(user, field)
                new_value = data[field]

                # Skip if no change
                if str(original_value) == str(new_value):
                    continue

                # Check uniqueness for username and email
                if field == 'username' and new_value != user.username:
                    existing = User.query.filter_by(username=new_value).first()
                    if existing:
                        return False, "Username already taken"

                if field == 'email' and new_value != user.email:
                    existing = User.query.filter_by(email=new_value).first()
                    if existing:
                        return False, "Email already in use"

                original_values[field] = str(original_value) if original_value else None
                updated_values[field] = str(new_value) if new_value else None
                setattr(user, field, new_value)

        if not updated_values:
            return True, "No changes made"

        db.session.commit()

        # Log the action
        AdminService.log_admin_action(
            admin_id=admin_id,
            action='user_update',
            target_type='user',
            target_id=user_id,
            details={
                'before': original_values,
                'after': updated_values
            }
        )

        return True, "User updated successfully"

    @staticmethod
    def delete_user(admin_id: int, user_id: int) -> tuple[bool, str]:
        """
        Delete user and all associated data, log the action.

        Args:
            admin_id: The admin performing the action
            user_id: The user to delete

        Returns:
            Tuple of (success, message)
        """
        # Prevent self-deletion
        if admin_id == user_id:
            return False, "Cannot delete your own account"

        user = User.query.get(user_id)
        if not user:
            return False, "User not found"

        # Store user info for audit log before deletion
        user_info = {
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin
        }

        # The cascade delete on User model will handle related data
        db.session.delete(user)
        db.session.commit()

        # Log the action
        AdminService.log_admin_action(
            admin_id=admin_id,
            action='user_delete',
            target_type='user',
            target_id=user_id,
            details={'deleted_user': user_info}
        )

        return True, f"User '{user_info['username']}' deleted successfully"

    @staticmethod
    def toggle_admin(admin_id: int, user_id: int) -> tuple[bool, str]:
        """
        Toggle admin status for a user.

        Args:
            admin_id: The admin performing the action
            user_id: The user to toggle

        Returns:
            Tuple of (success, message)
        """
        # Prevent self-modification
        if admin_id == user_id:
            return False, "Cannot modify your own admin status"

        user = User.query.get(user_id)
        if not user:
            return False, "User not found"

        original_status = user.is_admin
        user.is_admin = not user.is_admin
        db.session.commit()

        action = 'admin_grant' if user.is_admin else 'admin_revoke'

        AdminService.log_admin_action(
            admin_id=admin_id,
            action=action,
            target_type='user',
            target_id=user_id,
            details={
                'username': user.username,
                'before': original_status,
                'after': user.is_admin
            }
        )

        status_text = "granted" if user.is_admin else "revoked"
        return True, f"Admin status {status_text} for '{user.username}'"

    @staticmethod
    def get_all_groups(page: int = 1, per_page: int = 20, search: Optional[str] = None):
        """
        Get paginated list of all groups with optional search.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            search: Optional search term for group name

        Returns:
            Pagination object with groups
        """
        query = UserGroup.query

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    UserGroup.group_name.ilike(search_term),
                    UserGroup.group_description.ilike(search_term)
                )
            )

        return query.order_by(UserGroup.group_id).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @staticmethod
    def get_group_details(group_id: int):
        """
        Get detailed group info including members.

        Args:
            group_id: The group's ID

        Returns:
            dict with group details or None if not found
        """
        group = UserGroup.query.get(group_id)
        if not group:
            return None

        # Get members
        memberships = UserGroupMembership.query.filter_by(group_id=group_id).all()
        members = []
        for m in memberships:
            user = User.query.get(m.user_id)
            if user:
                members.append({
                    'user_id': user.user_id,
                    'username': user.username,
                    'role': m.role,
                    'joined_at': m.joined_at
                })

        # Get pending invitations count
        pending_invitations = GroupInvitation.query.filter_by(
            group_id=group_id, status='pending'
        ).count()

        # Get pending join requests count
        pending_requests = GroupJoinRequest.query.filter_by(
            group_id=group_id, status='pending'
        ).count()

        return {
            'group': group,
            'members': members,
            'member_count': len(members),
            'pending_invitations': pending_invitations,
            'pending_requests': pending_requests
        }

    @staticmethod
    def update_group(admin_id: int, group_id: int, data: dict) -> tuple[bool, str]:
        """
        Update group fields and log the action.

        Args:
            admin_id: The admin performing the action
            group_id: The group to update
            data: Dict with fields to update

        Returns:
            Tuple of (success, message)
        """
        group = UserGroup.query.get(group_id)
        if not group:
            return False, "Group not found"

        original_values = {}
        updated_values = {}

        allowed_fields = ['group_name', 'group_description']

        for field in allowed_fields:
            if field in data:
                original_value = getattr(group, field)
                new_value = data[field]

                if str(original_value) == str(new_value):
                    continue

                original_values[field] = str(original_value) if original_value else None
                updated_values[field] = str(new_value) if new_value else None
                setattr(group, field, new_value)

        if not updated_values:
            return True, "No changes made"

        db.session.commit()

        AdminService.log_admin_action(
            admin_id=admin_id,
            action='group_update',
            target_type='group',
            target_id=group_id,
            details={
                'before': original_values,
                'after': updated_values
            }
        )

        return True, "Group updated successfully"

    @staticmethod
    def delete_group(admin_id: int, group_id: int) -> tuple[bool, str]:
        """
        Delete group and memberships, log the action.

        Args:
            admin_id: The admin performing the action
            group_id: The group to delete

        Returns:
            Tuple of (success, message)
        """
        group = UserGroup.query.get(group_id)
        if not group:
            return False, "Group not found"

        group_info = {
            'group_name': group.group_name,
            'member_count': UserGroupMembership.query.filter_by(group_id=group_id).count()
        }

        # Delete memberships first
        UserGroupMembership.query.filter_by(group_id=group_id).delete()

        # Delete invitations
        GroupInvitation.query.filter_by(group_id=group_id).delete()

        # Delete join requests
        GroupJoinRequest.query.filter_by(group_id=group_id).delete()

        # Delete the group
        db.session.delete(group)
        db.session.commit()

        AdminService.log_admin_action(
            admin_id=admin_id,
            action='group_delete',
            target_type='group',
            target_id=group_id,
            details={'deleted_group': group_info}
        )

        return True, f"Group '{group_info['group_name']}' deleted successfully"

    @staticmethod
    def log_admin_action(
        admin_id: int,
        action: str,
        target_type: str,
        target_id: int,
        details: Optional[dict] = None
    ):
        """
        Create audit log entry.

        Args:
            admin_id: The admin performing the action
            action: Action type (user_update, user_delete, etc.)
            target_type: Target type (user, group)
            target_id: Target entity ID
            details: Optional dict with additional details
        """
        log_entry = AdminAuditLog(
            admin_user_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=json.dumps(details) if details else None
        )
        db.session.add(log_entry)
        db.session.commit()

    @staticmethod
    def get_audit_logs(
        page: int = 1,
        per_page: int = 50,
        admin_id: Optional[int] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None
    ):
        """
        Get paginated audit logs with optional filters.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            admin_id: Filter by admin user ID
            action: Filter by action type
            target_type: Filter by target type

        Returns:
            Pagination object with audit logs
        """
        query = AdminAuditLog.query

        if admin_id:
            query = query.filter_by(admin_user_id=admin_id)
        if action:
            query = query.filter_by(action=action)
        if target_type:
            query = query.filter_by(target_type=target_type)

        return query.order_by(AdminAuditLog.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @staticmethod
    def get_dashboard_stats():
        """
        Get overview statistics for admin dashboard.

        Returns:
            dict with various stats
        """
        total_users = User.query.count()
        admin_users = User.query.filter_by(is_admin=True).count()
        total_groups = UserGroup.query.count()
        total_workouts = Workout.query.count()
        completed_workouts = Workout.query.filter_by(is_completed=True).count()

        # Recent activity (last 7 days)
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_users = User.query.filter(User.created_at >= week_ago).count()
        recent_workouts = Workout.query.filter(Workout.created_at >= week_ago).count()

        return {
            'total_users': total_users,
            'admin_users': admin_users,
            'total_groups': total_groups,
            'total_workouts': total_workouts,
            'completed_workouts': completed_workouts,
            'recent_users': recent_users,
            'recent_workouts': recent_workouts
        }

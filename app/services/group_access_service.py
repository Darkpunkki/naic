"""
Group access helper methods.
"""

from app.models import UserGroupMembership


class GroupAccessService:
    @staticmethod
    def get_membership(user_id: int, group_id: int):
        return UserGroupMembership.query.filter_by(user_id=user_id, group_id=group_id).first()

    @staticmethod
    def is_member(user_id: int, group_id: int) -> bool:
        return GroupAccessService.get_membership(user_id, group_id) is not None

    @staticmethod
    def is_owner_or_admin(user_id: int, group_id: int) -> bool:
        membership = GroupAccessService.get_membership(user_id, group_id)
        return bool(membership and membership.role in ('owner', 'admin'))

    @staticmethod
    def group_member_ids(group_id: int) -> list[int]:
        memberships = UserGroupMembership.query.filter_by(group_id=group_id).all()
        return [membership.user_id for membership in memberships]

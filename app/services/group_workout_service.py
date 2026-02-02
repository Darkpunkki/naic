"""
Group workout browsing and access checks.
"""

from datetime import datetime, time

from app.models import Workout
from app.services.group_access_service import GroupAccessService


class GroupWorkoutService:
    DEFAULT_PAGE_SIZE = 15
    MAX_PAGE_SIZE = 100

    @staticmethod
    def parse_completed_filter(raw_value: str):
        if raw_value is None or raw_value == '' or raw_value == 'all':
            return None
        value = str(raw_value).strip().lower()
        if value in {'true', '1', 'yes', 'completed'}:
            return True
        if value in {'false', '0', 'no', 'incomplete'}:
            return False
        return None

    @staticmethod
    def _normalize_pagination(page: int, page_size: int) -> tuple[int, int]:
        page = max(1, int(page or 1))
        page_size = int(page_size or GroupWorkoutService.DEFAULT_PAGE_SIZE)
        page_size = max(1, min(GroupWorkoutService.MAX_PAGE_SIZE, page_size))
        return page, page_size

    @staticmethod
    def list_group_workouts(
        group_id: int,
        viewer_user_id: int,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        member_user_id: int = None,
        completed=None,
        start_date=None,
        end_date=None,
    ) -> dict:
        if not GroupAccessService.is_member(viewer_user_id, group_id):
            raise PermissionError("You are not a member of this group.")

        page, page_size = GroupWorkoutService._normalize_pagination(page, page_size)
        member_ids = GroupAccessService.group_member_ids(group_id)

        query = Workout.query.filter(Workout.user_id.in_(member_ids))

        if member_user_id and member_user_id in member_ids:
            query = query.filter(Workout.user_id == member_user_id)

        if completed is True:
            query = query.filter(Workout.is_completed == True)
        elif completed is False:
            query = query.filter(Workout.is_completed == False)

        if start_date:
            query = query.filter(Workout.workout_date >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.filter(Workout.workout_date <= datetime.combine(end_date, time.max))

        total = query.count()
        workouts = (
            query.order_by(Workout.workout_date.desc(), Workout.workout_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "workouts": workouts,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "member_ids": member_ids,
        }

    @staticmethod
    def get_group_workout(group_id: int, workout_id: int, viewer_user_id: int):
        if not GroupAccessService.is_member(viewer_user_id, group_id):
            raise PermissionError("You are not a member of this group.")

        workout = Workout.query.get(workout_id)
        if not workout:
            raise LookupError("Workout not found.")

        member_ids = GroupAccessService.group_member_ids(group_id)
        if workout.user_id not in member_ids:
            raise PermissionError("Workout is not visible in this group.")

        return workout

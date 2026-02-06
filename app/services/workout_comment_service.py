"""
Workout comment helper methods.
"""

from datetime import timezone

from app.models import WorkoutComment, db


class WorkoutCommentService:
    MAX_COMMENT_LENGTH = 2000
    DELETED_BODY = "[deleted]"

    @staticmethod
    def _normalize_body(body: str) -> str:
        if body is None:
            raise ValueError("Comment body is required.")

        cleaned = str(body).strip()
        if not cleaned:
            raise ValueError("Comment cannot be empty.")
        if len(cleaned) > WorkoutCommentService.MAX_COMMENT_LENGTH:
            raise ValueError(f"Comment must be at most {WorkoutCommentService.MAX_COMMENT_LENGTH} characters.")

        return cleaned

    @staticmethod
    def list_comments(group_id: int, workout_id: int):
        return (
            WorkoutComment.query.filter_by(group_id=group_id, workout_id=workout_id)
            .order_by(WorkoutComment.created_at.asc(), WorkoutComment.comment_id.asc())
            .all()
        )

    @staticmethod
    def serialize_comment(comment: WorkoutComment, viewer_user_id: int = None, can_moderate: bool = False) -> dict:
        is_author = bool(viewer_user_id and viewer_user_id == comment.author_user_id)
        def to_utc_iso(value):
            if not value:
                return None
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
            return value.isoformat().replace("+00:00", "Z")

        return {
            "comment_id": comment.comment_id,
            "group_id": comment.group_id,
            "workout_id": comment.workout_id,
            "author_user_id": comment.author_user_id,
            "author_username": comment.author.username if comment.author else "Unknown",
            "body": comment.body,
            "is_deleted": bool(comment.is_deleted),
            "created_at": to_utc_iso(comment.created_at),
            "updated_at": to_utc_iso(comment.updated_at),
            "can_edit": is_author and not comment.is_deleted,
            "can_delete": (is_author or can_moderate) and not comment.is_deleted,
        }

    @staticmethod
    def create_comment(group_id: int, workout_id: int, author_user_id: int, body: str):
        cleaned_body = WorkoutCommentService._normalize_body(body)

        comment = WorkoutComment(
            group_id=group_id,
            workout_id=workout_id,
            author_user_id=author_user_id,
            body=cleaned_body,
            is_deleted=False,
        )
        db.session.add(comment)
        db.session.commit()
        return comment

    @staticmethod
    def update_comment(comment: WorkoutComment, body: str):
        if comment.is_deleted:
            raise ValueError("Deleted comments cannot be edited.")

        comment.body = WorkoutCommentService._normalize_body(body)
        db.session.commit()
        return comment

    @staticmethod
    def soft_delete_comment(comment: WorkoutComment):
        if not comment.is_deleted:
            comment.is_deleted = True
            comment.body = WorkoutCommentService.DELETED_BODY
            db.session.commit()
        return comment

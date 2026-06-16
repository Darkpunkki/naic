"""REST API endpoints (/api/v1) — thin transport over the service layer.

Every authenticated endpoint scopes data to ``g.current_user`` (resolved from the
bearer token); a caller can never act on another user's data.
"""
from datetime import datetime

from flask import jsonify, request, g

from app.api import api_bp
from app.api.auth import require_api_token
from app.models import Workout
from app.services.workout_service import WorkoutService


def _serialize_set(s):
    return {
        "set_id": s.set_id,
        "set_order": s.set_order,
        "status": s.status,
        "reps": s.reps[0].rep_count if s.reps else None,
        "weight": float(s.weights[0].weight_value) if s.weights else None,
        "is_bodyweight": bool(s.weights[0].is_bodyweight) if s.weights else False,
    }


def _serialize_movement(wm):
    return {
        "workout_movement_id": wm.workout_movement_id,
        "name": wm.movement.movement_name,
        "is_completed": wm.is_completed,
        "sets": [_serialize_set(s) for s in wm.sets],
    }


def _serialize_workout(workout, include_movements=False):
    data = {
        "workout_id": workout.workout_id,
        "name": workout.workout_name,
        "date": workout.workout_date.strftime("%Y-%m-%d") if workout.workout_date else None,
        "is_completed": workout.is_completed,
        "workout_group_id": workout.workout_group_id,
    }
    if include_movements:
        data["movements"] = [_serialize_movement(wm) for wm in workout.workout_movements]
    return data


@api_bp.get("/health")
def health():
    """Liveness check (no auth)."""
    return jsonify({"status": "ok"})


@api_bp.get("/me")
@require_api_token
def me():
    """Identify the user the presented token belongs to."""
    user = g.current_user
    return jsonify({
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
    })


@api_bp.get("/workouts")
@require_api_token
def list_workouts():
    """List the token owner's workouts. Optional ?completed=true|false filter."""
    completed = request.args.get("completed")
    filter_completed = None
    if completed == "true":
        filter_completed = True
    elif completed == "false":
        filter_completed = False

    workouts = WorkoutService.get_user_workouts(g.current_user.user_id, filter_completed)
    return jsonify({"workouts": [_serialize_workout(w) for w in workouts]})


@api_bp.get("/workouts/<int:workout_id>")
@require_api_token
def get_workout(workout_id):
    """Fetch one workout (with movements/sets), scoped to the token owner."""
    workout = Workout.query.get(workout_id)
    if workout is None or workout.user_id != g.current_user.user_id:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_serialize_workout(workout, include_movements=True))


@api_bp.post("/workouts")
@require_api_token
def create_workout():
    """Create a workout from an agent-provided plan (no OpenAI call).

    Body: {"workout_name": str, "date": "YYYY-MM-DD"?, "movements": [
        {"name": str, "sets": int, "reps": int, "weight": float,
         "is_bodyweight": bool?, "muscle_groups": [{"name": str, "impact": int}]?}
    ]}. Movements already in the catalog reuse their stored muscle-group impacts.
    """
    plan = request.get_json(silent=True)
    if not isinstance(plan, dict) or not plan.get("movements"):
        return jsonify({
            "error": "invalid_plan",
            "message": "Body must be a JSON object with a non-empty 'movements' list.",
        }), 400

    workout_date = None
    date_str = plan.get("date")
    if date_str:
        try:
            workout_date = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return jsonify({"error": "invalid_date", "message": "date must be 'YYYY-MM-DD'."}), 400

    workout = WorkoutService.create_workout_from_plan(
        g.current_user.user_id, plan, workout_date
    )
    return jsonify(_serialize_workout(workout, include_movements=True)), 201

"""REST API endpoints (/api/v1) — thin transport over the service layer.

Every authenticated endpoint scopes data to ``g.current_user`` (resolved from the
bearer token); a caller can never act on another user's data.
"""
from datetime import datetime

from flask import jsonify, request, g

from app.api import api_bp
from app.api.auth import require_api_token
from app.models import Workout, Movement, MuscleGroup
from app.services.workout_service import WorkoutService
# Reuse the muscle-group aggregation helpers already powering the /stats/data page.
from app.routes.stats import (
    _normalize_period,
    _period_range,
    _query_muscle_totals,
    _query_total_series,
    _build_changes,
)
# Reuse the leaderboard computation shared with the /leaderboard/data page.
from app.routes.leaderboard import build_leaderboard


# --- serializers / helpers ---

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


def _serialize_catalog_movement(m):
    """A catalog movement with its muscle-group split in the same shape a plan uses
    (``{name, impact}``), so the agent can copy it straight into a new plan."""
    return {
        "movement_id": m.movement_id,
        "name": m.movement_name,
        "muscle_groups": [
            {"name": mmg.muscle_group.muscle_group_name, "impact": mmg.target_percentage}
            for mmg in m.muscle_groups
        ],
    }


def _owned_workout_or_none(workout_id):
    w = Workout.query.get(workout_id)
    if w is None or w.user_id != g.current_user.user_id:
        return None
    return w


def _parse_date(value):
    """Return (date_or_None, error_or_None). Empty input is not an error."""
    if not value:
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except (ValueError, TypeError):
        return None, "must be 'YYYY-MM-DD'"


def _as_date(value):
    return value.date() if isinstance(value, datetime) else value


# --- identity ---

@api_bp.get("/health")
def health():
    """Liveness check (no auth)."""
    return jsonify({"status": "ok"})


@api_bp.get("/me")
@require_api_token
def me():
    """Identify the token owner, including the fitness profile used to tailor plans."""
    user = g.current_user
    return jsonify({
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "profile": {
            "sex": user.sex,
            "bodyweight": float(user.bodyweight) if user.bodyweight is not None else None,
            "gym_experience": user.gym_experience,
            "workout_goal": user.workout_goal,
        },
    })


# --- catalog (read-only reference data) ---

@api_bp.get("/movements")
@require_api_token
def list_movements():
    """The movement catalog with muscle-group splits the agent builds plans from."""
    movements = sorted(Movement.query.all(), key=lambda m: m.movement_name)
    return jsonify({"movements": [_serialize_catalog_movement(m) for m in movements]})


@api_bp.get("/muscle-groups")
@require_api_token
def list_muscle_groups():
    """Canonical muscle-group names (use these in a plan's muscle_groups)."""
    groups = sorted(MuscleGroup.query.all(), key=lambda mg: mg.muscle_group_name)
    return jsonify({"muscle_groups": [
        {"muscle_group_id": mg.muscle_group_id, "name": mg.muscle_group_name} for mg in groups
    ]})


# --- workouts ---

@api_bp.get("/workouts")
@require_api_token
def list_workouts():
    """List the token owner's workouts (all states).

    Optional filters: ?completed=true|false, ?from=YYYY-MM-DD, ?to=YYYY-MM-DD.
    """
    completed = request.args.get("completed")
    filter_completed = None
    if completed == "true":
        filter_completed = True
    elif completed == "false":
        filter_completed = False

    date_from, err_from = _parse_date(request.args.get("from"))
    date_to, err_to = _parse_date(request.args.get("to"))
    if err_from or err_to:
        return jsonify({"error": "invalid_date", "message": f"'from'/'to' {err_from or err_to}"}), 400

    workouts = WorkoutService.get_user_workouts(g.current_user.user_id, filter_completed)

    if date_from or date_to:
        def in_range(w):
            d = _as_date(w.workout_date)
            if d is None:
                return False
            if date_from and d < date_from:
                return False
            if date_to and d > date_to:
                return False
            return True
        workouts = [w for w in workouts if in_range(w)]

    return jsonify({"workouts": [_serialize_workout(w) for w in workouts]})


@api_bp.get("/workouts/<int:workout_id>")
@require_api_token
def get_workout(workout_id):
    """Fetch one workout (with movements/sets), scoped to the token owner."""
    workout = _owned_workout_or_none(workout_id)
    if workout is None:
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

    workout_date, err = _parse_date(plan.get("date"))
    if err:
        return jsonify({"error": "invalid_date", "message": f"date {err}"}), 400

    workout = WorkoutService.create_workout_from_plan(
        g.current_user.user_id, plan, workout_date
    )
    return jsonify(_serialize_workout(workout, include_movements=True)), 201


@api_bp.patch("/workouts/<int:workout_id>")
@require_api_token
def update_workout(workout_id):
    """Reschedule (``date``) and/or rename (``name``) a workout."""
    workout = _owned_workout_or_none(workout_id)
    if workout is None:
        return jsonify({"error": "not_found"}), 404

    data = request.get_json(silent=True) or {}
    if "date" in data:
        new_date, err = _parse_date(data.get("date"))
        if err or new_date is None:
            return jsonify({"error": "invalid_date", "message": "date must be 'YYYY-MM-DD'"}), 400
        WorkoutService.update_workout_date(workout_id, new_date)
    if data.get("name"):
        WorkoutService.update_workout_name(workout_id, data["name"])

    return jsonify(_serialize_workout(Workout.query.get(workout_id), include_movements=True))


@api_bp.delete("/workouts/<int:workout_id>")
@require_api_token
def delete_workout(workout_id):
    """Delete a workout owned by the token owner."""
    workout = _owned_workout_or_none(workout_id)
    if workout is None:
        return jsonify({"error": "not_found"}), 404
    WorkoutService.delete_workout(workout_id)
    return "", 204


# --- stats ---

@api_bp.get("/stats")
@require_api_token
def stats():
    """The token owner's muscle-group volume summary for a period.

    Query: ?period=week|month|all (default all). Mirrors the dashboard /stats/data:
    totals per muscle group, period-over-period changes, and a daily volume series.
    """
    period = _normalize_period(request.args.get("period"))
    cur_start, cur_end, prev_start, prev_end = _period_range(period)
    uid = g.current_user.user_id

    current = _query_muscle_totals(uid, cur_start, cur_end)
    previous = _query_muscle_totals(uid, prev_start, prev_end)

    return jsonify({
        "period": period,
        "range": {"start": cur_start.strftime("%Y-%m-%d"), "end": cur_end.strftime("%Y-%m-%d")},
        "totals_by_muscle": current,
        "changes": _build_changes(current, previous),
        "series": _query_total_series(uid, cur_start, cur_end),
    })


@api_bp.get("/leaderboard")
@require_api_token
def leaderboard():
    """Group-scoped leaderboard rankings for the token owner.

    Query: ?period=week|month|all (default week), ?group_id=<id> (optional; must be a
    group the user belongs to). Without group_id, ranks everyone who shares a group
    with the user. Returns per-user volume distribution, totals, balance, and averages.
    """
    payload, error = build_leaderboard(
        g.current_user.user_id,
        request.args.get("group_id", type=int),
        request.args.get("period", "week"),
    )
    if error:
        return jsonify({"error": error[0]}), error[1]
    return jsonify(payload)

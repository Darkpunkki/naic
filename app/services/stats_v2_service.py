from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func

from app.models import (
    db,
    Workout,
    WorkoutMovement,
    Set,
    SetEntry,
    Movement,
    MuscleGroup,
    WorkoutMuscleGroupImpact,
    WorkoutSessionSummary,
    WorkoutMovementStats,
    MovementDailySummary,
    MuscleGroupDailySummary,
    PersonalRecord,
    BodyweightLog,
)
from app.services.stats_service import StatsService
from app.services.feedback_service import MUSCLE_PAIRS


class StatsV2Service:
    """Aggregate and store richer stats summaries for the stats revamp."""

    _cache: Dict[str, Tuple[float, dict]] = {}
    _cache_ttl_seconds = 60

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _tonnage_load(weight_value: float, is_bodyweight: bool, user_bodyweight: float) -> float:
        external = max(0.0, StatsV2Service._safe_float(weight_value))
        bodyweight = max(0.0, StatsV2Service._safe_float(user_bodyweight))
        return external + (bodyweight if is_bodyweight else 0.0)

    @staticmethod
    def _epley_1rm(weight_value: float, reps: int) -> float:
        if reps <= 0:
            return 0.0
        return weight_value * (1.0 + (reps / 30.0))

    @staticmethod
    def clear_cache_for_user(user_id: int) -> None:
        keys_to_remove = [key for key in StatsV2Service._cache if key.startswith(f"user:{user_id}:")]
        for key in keys_to_remove:
            StatsV2Service._cache.pop(key, None)

    @staticmethod
    def _cache_get(key: str) -> Optional[dict]:
        item = StatsV2Service._cache.get(key)
        if not item:
            return None
        timestamp, payload = item
        if (datetime.utcnow().timestamp() - timestamp) > StatsV2Service._cache_ttl_seconds:
            StatsV2Service._cache.pop(key, None)
            return None
        return payload

    @staticmethod
    def _cache_set(key: str, payload: dict) -> None:
        StatsV2Service._cache[key] = (datetime.utcnow().timestamp(), payload)

    @staticmethod
    def process_completed_workout(workout_id: int) -> None:
        workout = Workout.query.get(workout_id)
        if not workout or not workout.is_completed:
            return

        StatsV2Service.rebuild_workout_summaries(workout)
        StatsV2Service.clear_cache_for_user(workout.user_id)

    @staticmethod
    def rebuild_workout_summaries(workout: Workout) -> None:
        # Remove existing summaries for this workout to keep idempotent
        WorkoutSessionSummary.query.filter_by(workout_id=workout.workout_id).delete()
        WorkoutMovementStats.query.filter_by(workout_id=workout.workout_id).delete()
        db.session.flush()

        movement_stats = StatsV2Service._build_workout_movement_stats(workout)
        for stats in movement_stats:
            db.session.add(stats)

        session_summary = StatsV2Service._build_workout_session_summary(workout, movement_stats)
        db.session.add(session_summary)

        db.session.commit()

        StatsV2Service.rebuild_daily_summaries_for_date(workout.user_id, workout.workout_date.date())
        StatsV2Service._update_personal_records(workout, movement_stats)
        StatsV2Service._log_bodyweight_for_workout(workout)
        StatsV2Service.clear_cache_for_user(workout.user_id)

    @staticmethod
    def rebuild_daily_summaries_for_date(user_id: int, summary_date: date) -> None:
        MovementDailySummary.query.filter_by(user_id=user_id, summary_date=summary_date).delete()
        MuscleGroupDailySummary.query.filter_by(user_id=user_id, summary_date=summary_date).delete()
        db.session.flush()

        movement_rows = (
            db.session.query(
                WorkoutMovementStats.movement_id,
                func.coalesce(func.sum(WorkoutMovementStats.total_volume), 0),
                func.coalesce(func.sum(WorkoutMovementStats.total_tonnage), 0),
                func.coalesce(func.sum(WorkoutMovementStats.total_reps), 0),
                func.coalesce(func.sum(WorkoutMovementStats.total_sets), 0),
                func.coalesce(func.max(WorkoutMovementStats.e1rm), 0),
                func.coalesce(func.max(WorkoutMovementStats.max_weight), 0),
                func.coalesce(func.avg(WorkoutMovementStats.avg_rpe), 0),
                func.coalesce(func.avg(WorkoutMovementStats.avg_rest_seconds), 0),
                func.count(WorkoutMovementStats.stats_id),
            )
            .filter(WorkoutMovementStats.user_id == user_id)
            .filter(func.date(WorkoutMovementStats.workout_date) == summary_date)
            .group_by(WorkoutMovementStats.movement_id)
            .all()
        )

        for row in movement_rows:
            (
                movement_id,
                total_volume,
                total_tonnage,
                total_reps,
                total_sets,
                e1rm_max,
                max_weight,
                avg_rpe,
                avg_rest,
                sessions,
            ) = row
            summary = MovementDailySummary(
                user_id=user_id,
                movement_id=movement_id,
                summary_date=summary_date,
                total_volume=total_volume,
                total_tonnage=total_tonnage,
                total_reps=total_reps,
                total_sets=total_sets,
                e1rm_max=e1rm_max,
                max_weight=max_weight,
                avg_rpe=avg_rpe if avg_rpe else None,
                avg_rest_seconds=avg_rest if avg_rest else None,
                sessions=sessions,
            )
            db.session.add(summary)

        muscle_rows = (
            db.session.query(
                WorkoutMuscleGroupImpact.muscle_group_id,
                func.coalesce(func.sum(WorkoutMuscleGroupImpact.total_volume), 0),
                func.coalesce(func.sum(WorkoutMuscleGroupImpact.total_reps), 0),
                func.coalesce(func.sum(WorkoutMuscleGroupImpact.total_sets), 0),
                func.count(WorkoutMuscleGroupImpact.impact_id),
            )
            .join(Workout, Workout.workout_id == WorkoutMuscleGroupImpact.workout_id)
            .filter(Workout.user_id == user_id)
            .filter(Workout.is_completed == True)
            .filter(func.date(Workout.workout_date) == summary_date)
            .group_by(WorkoutMuscleGroupImpact.muscle_group_id)
            .all()
        )

        for row in muscle_rows:
            muscle_group_id, total_volume, total_reps, total_sets, sessions = row
            summary = MuscleGroupDailySummary(
                user_id=user_id,
                muscle_group_id=muscle_group_id,
                summary_date=summary_date,
                total_volume=total_volume,
                total_reps=total_reps,
                total_sets=total_sets,
                sessions=sessions,
            )
            db.session.add(summary)

        db.session.commit()

    @staticmethod
    def _build_workout_movement_stats(workout: Workout) -> List[WorkoutMovementStats]:
        movement_stats: List[WorkoutMovementStats] = []
        user_bodyweight = StatsV2Service._safe_float(getattr(workout.user, "bodyweight", 0))

        for wm in workout.workout_movements:
            total_volume = 0.0
            total_tonnage = 0.0
            total_reps = 0.0
            total_sets = len(wm.sets)
            completed_sets = 0
            skipped_sets = 0
            weights = []
            e1rm_max = 0.0
            top_set_weight = None
            top_set_reps = None
            rpe_values = []
            rest_values = []

            for single_set in wm.sets:
                status = getattr(single_set, "status", "pending")
                if status == "skipped":
                    skipped_sets += 1
                    continue
                if status == "completed":
                    completed_sets += 1

                entries = StatsService.iter_set_entries(single_set)
                if not entries:
                    continue

                # Rest/RPE stored on SetEntry (use first entry as set-level data)
                if single_set.entries:
                    entry_meta = single_set.entries[0]
                    if entry_meta.rpe is not None:
                        rpe_values.append(float(entry_meta.rpe))
                    if entry_meta.rest_seconds is not None:
                        rest_values.append(int(entry_meta.rest_seconds))

                for entry in entries:
                    reps = max(0, int(entry["reps"]))
                    if reps <= 0:
                        continue
                    weight_value = StatsV2Service._safe_float(entry["weight_value"])
                    is_bodyweight = bool(entry["is_bodyweight"])

                    load = StatsService.effective_load(weight_value, is_bodyweight, user_bodyweight)
                    total_volume += reps * load

                    tonnage_load = StatsV2Service._tonnage_load(weight_value, is_bodyweight, user_bodyweight)
                    total_tonnage += reps * tonnage_load

                    total_reps += reps
                    weights.append(tonnage_load)

                    e1rm = StatsV2Service._epley_1rm(tonnage_load, reps)
                    if e1rm > e1rm_max:
                        e1rm_max = e1rm
                        top_set_weight = tonnage_load
                        top_set_reps = reps

            avg_weight = sum(weights) / len(weights) if weights else None
            max_weight = max(weights) if weights else None
            avg_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None
            total_rest_seconds = sum(rest_values) if rest_values else None
            avg_rest_seconds = total_rest_seconds / len(rest_values) if rest_values else None

            completion_rate = 0.0
            total_non_pending = completed_sets + skipped_sets
            if total_non_pending > 0:
                completion_rate = completed_sets / total_non_pending

            movement_stats.append(
                WorkoutMovementStats(
                    workout_id=workout.workout_id,
                    user_id=workout.user_id,
                    movement_id=wm.movement_id,
                    workout_movement_id=wm.workout_movement_id,
                    workout_date=workout.workout_date,
                    total_volume=round(total_volume, 2),
                    total_tonnage=round(total_tonnage, 2),
                    total_reps=round(total_reps, 2),
                    total_sets=total_sets,
                    completed_sets=completed_sets,
                    skipped_sets=skipped_sets,
                    avg_weight=round(avg_weight, 2) if avg_weight is not None else None,
                    max_weight=round(max_weight, 2) if max_weight is not None else None,
                    e1rm=round(e1rm_max, 2) if e1rm_max else None,
                    top_set_reps=top_set_reps,
                    top_set_weight=round(top_set_weight, 2) if top_set_weight is not None else None,
                    avg_rpe=round(avg_rpe, 2) if avg_rpe is not None else None,
                    total_rest_seconds=total_rest_seconds,
                    avg_rest_seconds=round(avg_rest_seconds, 2) if avg_rest_seconds is not None else None,
                    completion_rate=round(completion_rate, 3),
                )
            )

        return movement_stats

    @staticmethod
    def _build_workout_session_summary(
        workout: Workout,
        movement_stats: List[WorkoutMovementStats]
    ) -> WorkoutSessionSummary:
        total_volume = sum(StatsV2Service._safe_float(ms.total_volume) for ms in movement_stats)
        total_tonnage = sum(StatsV2Service._safe_float(ms.total_tonnage) for ms in movement_stats)
        total_reps = sum(StatsV2Service._safe_float(ms.total_reps) for ms in movement_stats)
        total_sets = sum(int(ms.total_sets or 0) for ms in movement_stats)
        completed_sets = sum(int(ms.completed_sets or 0) for ms in movement_stats)
        skipped_sets = sum(int(ms.skipped_sets or 0) for ms in movement_stats)
        avg_rpe_values = [float(ms.avg_rpe) for ms in movement_stats if ms.avg_rpe is not None]
        avg_rest_values = [float(ms.avg_rest_seconds) for ms in movement_stats if ms.avg_rest_seconds is not None]

        completion_rate = 0.0
        if completed_sets + skipped_sets > 0:
            completion_rate = completed_sets / (completed_sets + skipped_sets)

        duration_seconds = None
        if workout.started_at and workout.completed_at:
            duration_seconds = int((workout.completed_at - workout.started_at).total_seconds())
            if duration_seconds < 0:
                duration_seconds = None

        return WorkoutSessionSummary(
            workout_id=workout.workout_id,
            user_id=workout.user_id,
            workout_date=workout.workout_date,
            total_volume=round(total_volume, 2),
            total_tonnage=round(total_tonnage, 2),
            total_reps=round(total_reps, 2),
            total_sets=total_sets,
            total_movements=len(movement_stats),
            completed_sets=completed_sets,
            skipped_sets=skipped_sets,
            completion_rate=round(completion_rate, 3),
            avg_rpe=round(sum(avg_rpe_values) / len(avg_rpe_values), 2) if avg_rpe_values else None,
            avg_rest_seconds=round(sum(avg_rest_values) / len(avg_rest_values), 2) if avg_rest_values else None,
            duration_seconds=duration_seconds,
        )

    @staticmethod
    def _update_personal_records(workout: Workout, movement_stats: List[WorkoutMovementStats]) -> None:
        for stats in movement_stats:
            if stats.e1rm:
                StatsV2Service._upsert_pr(
                    user_id=workout.user_id,
                    movement_id=stats.movement_id,
                    record_type="e1rm",
                    value=float(stats.e1rm),
                    reps=stats.top_set_reps,
                    weight_value=float(stats.top_set_weight) if stats.top_set_weight else None,
                    workout_id=workout.workout_id,
                )
            if stats.max_weight:
                StatsV2Service._upsert_pr(
                    user_id=workout.user_id,
                    movement_id=stats.movement_id,
                    record_type="max_weight",
                    value=float(stats.max_weight),
                    reps=None,
                    weight_value=float(stats.max_weight),
                    workout_id=workout.workout_id,
                )
            if stats.total_reps:
                StatsV2Service._upsert_pr(
                    user_id=workout.user_id,
                    movement_id=stats.movement_id,
                    record_type="max_reps",
                    value=float(stats.total_reps),
                    reps=int(stats.total_reps),
                    weight_value=None,
                    workout_id=workout.workout_id,
                )
            if stats.total_volume:
                StatsV2Service._upsert_pr(
                    user_id=workout.user_id,
                    movement_id=stats.movement_id,
                    record_type="max_volume",
                    value=float(stats.total_volume),
                    reps=None,
                    weight_value=None,
                    workout_id=workout.workout_id,
                )

        db.session.commit()

    @staticmethod
    def _upsert_pr(
        user_id: int,
        movement_id: int,
        record_type: str,
        value: float,
        reps: Optional[int],
        weight_value: Optional[float],
        workout_id: Optional[int],
    ) -> None:
        existing = PersonalRecord.query.filter_by(
            user_id=user_id,
            movement_id=movement_id,
            record_type=record_type,
        ).first()

        achieved_at = datetime.utcnow()
        if workout_id:
            workout = Workout.query.get(workout_id)
            if workout and workout.workout_date:
                achieved_at = workout.workout_date

        if not existing:
            record = PersonalRecord(
                user_id=user_id,
                movement_id=movement_id,
                record_type=record_type,
                value=Decimal(str(round(value, 2))),
                reps=reps,
                weight_value=Decimal(str(round(weight_value, 2))) if weight_value is not None else None,
                workout_id=workout_id,
                achieved_at=achieved_at,
            )
            db.session.add(record)
            return

        if value > float(existing.value):
            existing.value = Decimal(str(round(value, 2)))
            existing.reps = reps
            existing.weight_value = Decimal(str(round(weight_value, 2))) if weight_value is not None else None
            existing.workout_id = workout_id
            existing.achieved_at = achieved_at

    @staticmethod
    def _log_bodyweight_for_workout(workout: Workout) -> None:
        user = workout.user
        if not user or user.bodyweight is None:
            return

        log_date = workout.workout_date.date() if workout.workout_date else date.today()
        existing = (
            BodyweightLog.query
            .filter(BodyweightLog.user_id == user.user_id)
            .filter(func.date(BodyweightLog.recorded_at) == log_date)
            .first()
        )
        if existing:
            return

        log = BodyweightLog(
            user_id=user.user_id,
            bodyweight=user.bodyweight,
            recorded_at=workout.workout_date or datetime.utcnow(),
            source="workout",
        )
        db.session.add(log)
        db.session.commit()

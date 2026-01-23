from __future__ import annotations

from typing import Dict, List, Tuple


class StatsService:
    DEFAULT_CONFIG = {
        "base_load": 10.0,
        "external_weight_factor": 1.0,
        "bodyweight_factor": 0.25,
        "min_effective_load": 0.0,
    }

    @staticmethod
    def get_config() -> Dict[str, float]:
        config = dict(StatsService.DEFAULT_CONFIG)
        try:
            from flask import current_app
            if current_app:
                config["base_load"] = float(current_app.config.get("IMPACT_BASE_LOAD", config["base_load"]))
                config["external_weight_factor"] = float(
                    current_app.config.get("IMPACT_EXTERNAL_WEIGHT_FACTOR", config["external_weight_factor"])
                )
                config["bodyweight_factor"] = float(
                    current_app.config.get("IMPACT_BODYWEIGHT_FACTOR", config["bodyweight_factor"])
                )
                config["min_effective_load"] = float(
                    current_app.config.get("IMPACT_MIN_EFFECTIVE_LOAD", config["min_effective_load"])
                )
        except RuntimeError:
            pass
        return config

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def effective_load(weight_value: float, is_bodyweight: bool, user_bodyweight: float) -> float:
        cfg = StatsService.get_config()
        external = max(0.0, StatsService._safe_float(weight_value))
        bodyweight = max(0.0, StatsService._safe_float(user_bodyweight))

        effective = cfg["base_load"] + (external * cfg["external_weight_factor"])
        if is_bodyweight:
            effective += bodyweight * cfg["bodyweight_factor"]

        return max(cfg["min_effective_load"], effective)

    @staticmethod
    def normalize_muscle_groups(muscle_group_assocs) -> List[Tuple[object, float]]:
        weighted = []
        total = 0.0
        for assoc in muscle_group_assocs:
            pct = max(0.0, StatsService._safe_float(getattr(assoc, "target_percentage", 0)))
            if pct <= 0:
                continue
            weighted.append((assoc, pct))
            total += pct
        if total <= 0:
            return []
        return [(assoc, pct / total) for assoc, pct in weighted]

    @staticmethod
    def iter_set_entries(single_set) -> List[dict]:
        entries = getattr(single_set, "entries", None)
        if entries:
            sorted_entries = sorted(
                entries,
                key=lambda e: (
                    getattr(e, "entry_order", 0) or 0,
                    getattr(e, "entry_id", 0) or 0,
                ),
            )
            return [
                {
                    "reps": max(0, int(getattr(entry, "reps", 0) or 0)),
                    "weight_value": StatsService._safe_float(getattr(entry, "weight_value", 0)),
                    "is_bodyweight": bool(getattr(entry, "is_bodyweight", False)),
                }
                for entry in sorted_entries
            ]

        reps_list = [max(0, int(getattr(r, "rep_count", 0) or 0)) for r in getattr(single_set, "reps", [])]
        weights_list = [
            (
                StatsService._safe_float(getattr(w, "weight_value", 0)),
                bool(getattr(w, "is_bodyweight", False)),
            )
            for w in getattr(single_set, "weights", [])
        ]

        if not reps_list and not weights_list:
            return []

        if not reps_list:
            reps_list = [0]
        if not weights_list:
            weights_list = [(0.0, False)]

        max_len = max(len(reps_list), len(weights_list))
        combined = []
        for i in range(max_len):
            reps = reps_list[i] if i < len(reps_list) else reps_list[-1]
            weight_value, is_bodyweight = weights_list[i] if i < len(weights_list) else weights_list[-1]
            combined.append(
                {
                    "reps": reps,
                    "weight_value": weight_value,
                    "is_bodyweight": is_bodyweight,
                }
            )
        return combined

    @staticmethod
    def calculate_movement_totals(workout_movement) -> Dict[int, dict]:
        normalized = StatsService.normalize_muscle_groups(workout_movement.movement.muscle_groups)
        if not normalized:
            return {}

        user_bodyweight = StatsService._safe_float(getattr(workout_movement.workout.user, "bodyweight", 0))
        totals: Dict[int, dict] = {}

        for assoc, pct in normalized:
            mg_id = assoc.muscle_group_id
            totals[mg_id] = {
                "name": assoc.muscle_group.muscle_group_name,
                "volume": 0.0,
                "reps": 0.0,
                "sets": 0.0,
            }

        for single_set in workout_movement.sets:
            entries = StatsService.iter_set_entries(single_set)
            if not entries:
                continue

            set_has_reps = False
            for entry in entries:
                reps = max(0, int(entry["reps"]))
                if reps <= 0:
                    continue
                set_has_reps = True
                load = StatsService.effective_load(entry["weight_value"], entry["is_bodyweight"], user_bodyweight)
                volume = reps * load

                for assoc, pct in normalized:
                    mg_id = assoc.muscle_group_id
                    totals[mg_id]["volume"] += volume * pct
                    totals[mg_id]["reps"] += reps * pct

            if set_has_reps:
                for assoc, pct in normalized:
                    mg_id = assoc.muscle_group_id
                    totals[mg_id]["sets"] += 1.0 * pct

        return totals

    @staticmethod
    def calculate_muscle_group_impact(workout_movement) -> Dict[str, float]:
        totals = StatsService.calculate_movement_totals(workout_movement)
        return {data["name"]: data["volume"] for data in totals.values()}

    @staticmethod
    def build_workout_impacts(workout) -> Dict[int, dict]:
        totals: Dict[int, dict] = {}
        for wm in workout.workout_movements:
            movement_totals = StatsService.calculate_movement_totals(wm)
            for mg_id, data in movement_totals.items():
                if mg_id not in totals:
                    totals[mg_id] = {
                        "name": data["name"],
                        "volume": 0.0,
                        "reps": 0.0,
                        "sets": 0.0,
                    }
                totals[mg_id]["volume"] += data["volume"]
                totals[mg_id]["reps"] += data["reps"]
                totals[mg_id]["sets"] += data["sets"]
        return totals

    @staticmethod
    def sync_set_entry_from_set(single_set):
        from app.models import SetEntry

        reps = sum(getattr(r, "rep_count", 0) or 0 for r in getattr(single_set, "reps", []))
        weight_obj = getattr(single_set, "weights", [None])[0] if getattr(single_set, "weights", None) else None
        weight_value = getattr(weight_obj, "weight_value", 0) if weight_obj else 0
        is_bodyweight = bool(getattr(weight_obj, "is_bodyweight", False)) if weight_obj else False

        entry = None
        entries = getattr(single_set, "entries", [])
        if entries:
            entry = entries[0]
        else:
            entry = SetEntry(set_id=single_set.set_id, entry_order=1, reps=0, weight_value=0, is_bodyweight=False)

        entry.reps = max(0, int(reps))
        entry.weight_value = weight_value
        entry.is_bodyweight = is_bodyweight
        return entry

    @staticmethod
    def rebuild_workout_impacts(workout, commit: bool = True) -> None:
        from app.models import db, WorkoutMuscleGroupImpact

        WorkoutMuscleGroupImpact.query.filter_by(workout_id=workout.workout_id).delete()

        totals = StatsService.build_workout_impacts(workout)
        for mg_id, data in totals.items():
            impact = WorkoutMuscleGroupImpact(
                workout_id=workout.workout_id,
                muscle_group_id=mg_id,
                total_volume=data["volume"],
                total_reps=data["reps"],
                total_sets=data["sets"],
            )
            db.session.add(impact)

        if commit:
            db.session.commit()

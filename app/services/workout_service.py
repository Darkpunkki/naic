"""
Workout Service - Handles workout CRUD operations.
"""
import uuid
from datetime import date, datetime, timedelta
from typing import Optional, List

from app.models import db, Workout, WorkoutMovement
from app.services.movement_service import MovementService
from app.services.stats_service import StatsService


class WorkoutService:

    @staticmethod
    def create_blank_workout(user_id: int, workout_date: date, name: str = "New workout") -> Workout:
        """
        Create a new blank workout with no movements.
        """
        new_workout = Workout(
            user_id=user_id,
            workout_name=name,
            workout_date=workout_date,
            is_completed=False
        )
        db.session.add(new_workout)
        db.session.commit()
        return new_workout

    @staticmethod
    def create_workout_from_plan(user_id: int, plan: dict, workout_date: date = None) -> Workout:
        """
        Create a workout with all movements from an AI-generated plan.

        Args:
            user_id: The user creating the workout
            plan: Dict with 'workout_name' and 'movements' list
            workout_date: Optional date for the workout (defaults to now)

        Returns:
            Created Workout object
        """
        if workout_date is None:
            workout_date = datetime.now()

        workout_name = plan.get("workout_name", "Unnamed Workout")
        movements_list = plan.get("movements", [])

        # Create the workout
        new_workout = Workout(
            user_id=user_id,
            workout_name=workout_name,
            workout_date=workout_date,
            is_completed=False
        )
        db.session.add(new_workout)
        db.session.commit()

        # Populate movements
        MovementService.populate_workout_movements(new_workout.workout_id, movements_list)

        return new_workout

    @staticmethod
    def create_weekly_workouts_from_plan(
        user_id: int,
        weekly_plan: dict,
        start_date: date = None,
        day_spacing: int = 2,
        specific_dates: List[date] = None
    ) -> list:
        """
        Create multiple workouts from a weekly plan.

        Args:
            user_id: The user creating the workouts
            weekly_plan: Dict with 'weekly_plan' key containing list of workout dicts
            start_date: Starting date for the first workout (defaults to today)
            day_spacing: Days between workouts (default 2)
            specific_dates: Optional list of specific dates for each workout

        Returns:
            List of created Workout objects
        """
        if start_date is None:
            start_date = datetime.today().date()

        plan_list = weekly_plan.get("weekly_plan", [])
        created_workouts = []

        # Generate a group ID for this batch of workouts
        group_id = str(uuid.uuid4())

        for idx, workout_data in enumerate(plan_list):
            # Use specific dates if provided, otherwise calculate from spacing
            if specific_dates and idx < len(specific_dates):
                workout_date = specific_dates[idx]
            else:
                workout_date = start_date + timedelta(days=idx * day_spacing)

            workout_name = workout_data.get("workout_name", f"Workout Day {idx + 1}")
            movements_list = workout_data.get("movements", [])

            # Create the workout with group_id
            new_workout = Workout(
                user_id=user_id,
                workout_name=workout_name,
                workout_date=workout_date,
                is_completed=False,
                workout_group_id=group_id
            )
            db.session.add(new_workout)
            db.session.commit()

            # Populate movements
            MovementService.populate_workout_movements(new_workout.workout_id, movements_list)

            created_workouts.append(new_workout)

        return created_workouts

    @staticmethod
    def update_workout_data(workout_id: int, form_data: dict) -> Workout:
        """
        Update workout movement data (sets, reps, weights, done status).

        Args:
            workout_id: The workout to update
            form_data: Request form data with weight_X, rep_X, done_X keys

        Returns:
            Updated Workout object
        """
        workout = Workout.query.get_or_404(workout_id)

        for wm in workout.workout_movements:
            # Update sets/reps/weights
            for s in wm.sets:
                # Handle weight updates
                if s.weights:
                    w = s.weights[0]
                    weight_key = f"weight_{w.weight_id}"
                    bodyweight_key = f"is_bodyweight_{w.weight_id}"

                    if weight_key in form_data:
                        w.weight_value = float(form_data[weight_key])
                    w.is_bodyweight = (bodyweight_key in form_data)

                # Handle rep updates
                if s.reps:
                    rep = s.reps[0]
                    rep_key = f"rep_{s.set_id}"
                    if rep_key in form_data:
                        rep.rep_count = int(form_data[rep_key])

                entry = StatsService.sync_set_entry_from_set(s)
                db.session.add(entry)
            # Update done status
            done_key = f"done_{wm.workout_movement_id}"
            wm.done = (done_key in form_data)

        if workout.is_completed:
            StatsService.rebuild_workout_impacts(workout, commit=False)

        db.session.commit()
        return workout

    @staticmethod
    def complete_workout(workout_id: int, form_data: dict, completion_date: date = None) -> Workout:
        """
        Mark a workout as complete and update all movement data.

        Args:
            workout_id: The workout to complete
            form_data: Request form data with weight_X, rep_X, done_X keys
            completion_date: Date of completion (defaults to today)

        Returns:
            Updated Workout object
        """
        if completion_date is None:
            completion_date = datetime.now().date()

        workout = Workout.query.get_or_404(workout_id)
        workout.is_completed = True
        workout.workout_date = completion_date

        # Update all movements
        for wm in workout.workout_movements:
            done_key = f"done_{wm.workout_movement_id}"
            wm.done = (done_key in form_data)

            for s in wm.sets:
                # Update reps
                rep_key = f"rep_{s.set_id}"
                if rep_key in form_data:
                    if s.reps:
                        s.reps[0].rep_count = int(form_data[rep_key])

                # Update weights
                if s.weights:
                    w = s.weights[0]
                    weight_key = f"weight_{w.weight_id}"
                    if weight_key in form_data:
                        w.weight_value = float(form_data[weight_key])

                entry = StatsService.sync_set_entry_from_set(s)
                db.session.add(entry)

        StatsService.rebuild_workout_impacts(workout, commit=False)
        db.session.commit()
        return workout

    @staticmethod
    def delete_workout(workout_id: int) -> bool:
        """
        Delete a workout and all associated data.

        Returns True if successful.
        """
        workout = Workout.query.get_or_404(workout_id)
        db.session.delete(workout)
        db.session.commit()
        return True

    @staticmethod
    def update_workout_name(workout_id: int, new_name: str) -> Workout:
        """Update the name of a workout."""
        workout = Workout.query.get_or_404(workout_id)
        workout.workout_name = new_name
        db.session.commit()
        return workout

    @staticmethod
    def update_workout_date(workout_id: int, new_date: date) -> Workout:
        """Update the date of a workout."""
        workout = Workout.query.get_or_404(workout_id)
        workout.workout_date = new_date
        db.session.commit()
        return workout

    @staticmethod
    def get_workout_by_id(workout_id: int) -> Optional[Workout]:
        """Get a workout by ID or return None."""
        return Workout.query.get(workout_id)

    @staticmethod
    def get_user_workouts(user_id: int, filter_completed: Optional[bool] = None) -> list:
        """
        Get all workouts for a user with optional completion filter.

        Args:
            user_id: The user's ID
            filter_completed: If True, only completed. If False, only incomplete. If None, all.

        Returns:
            List of Workout objects ordered by date descending
        """
        query = Workout.query.filter_by(user_id=user_id)

        if filter_completed is True:
            query = query.filter_by(is_completed=True)
        elif filter_completed is False:
            query = query.filter_by(is_completed=False)

        return query.order_by(Workout.workout_date.desc()).all()

    @staticmethod
    def generate_and_add_movements(workout_id: int, plan: dict) -> Workout:
        """
        Add AI-generated movements to an existing workout.

        Args:
            workout_id: The workout to add movements to
            plan: Dict with 'workout_name' and 'movements' list

        Returns:
            Updated Workout object
        """
        workout = Workout.query.get_or_404(workout_id)

        # Optionally update workout name
        workout_name = plan.get("workout_name")
        if workout_name:
            workout.workout_name = workout_name

        # Populate movements
        movements_list = plan.get("movements", [])
        MovementService.populate_workout_movements(workout_id, movements_list)

        db.session.commit()
        return workout

    @staticmethod
    def serialize_workout_to_plan(workout: Workout) -> dict:
        """
        Serialize an existing workout to plan format for duplication.

        Args:
            workout: The Workout object to serialize

        Returns:
            Dict in the same format as AI-generated plans
        """
        movements = []
        for wm in workout.workout_movements:
            # Get sets info
            sets_count = len(wm.sets)
            reps = 0
            weight = 0.0
            is_bodyweight = False

            if wm.sets:
                first_set = wm.sets[0]
                if first_set.reps:
                    reps = first_set.reps[0].rep_count
                if first_set.weights:
                    weight = float(first_set.weights[0].weight_value)
                    is_bodyweight = first_set.weights[0].is_bodyweight

            # Get muscle groups
            muscle_groups = [
                {
                    'name': mmg.muscle_group.muscle_group_name,
                    'impact': mmg.target_percentage
                }
                for mmg in wm.movement.muscle_groups
            ]

            movements.append({
                'name': wm.movement.movement_name,
                'sets': sets_count,
                'reps': reps,
                'weight': weight,
                'is_bodyweight': is_bodyweight,
                'muscle_groups': muscle_groups
            })

        return {
            'workout_name': workout.workout_name,
            'movements': movements
        }

    @staticmethod
    def duplicate_workout(workout_id: int, user_id: int, target_date: date) -> Workout:
        """
        Create a copy of a single workout on a new date.

        Args:
            workout_id: The workout to duplicate
            user_id: The user creating the duplicate
            target_date: The date for the new workout

        Returns:
            The newly created Workout object
        """
        source_workout = Workout.query.get_or_404(workout_id)

        # Verify user owns this workout
        if source_workout.user_id != user_id:
            raise ValueError("Unauthorized to duplicate this workout")

        # Serialize the source workout to plan format
        plan = WorkoutService.serialize_workout_to_plan(source_workout)

        # Append "(Copy)" to the name
        plan['workout_name'] = f"{plan['workout_name']} (Copy)"

        # Create the new workout
        new_workout = WorkoutService.create_workout_from_plan(user_id, plan, target_date)

        return new_workout

    @staticmethod
    def duplicate_workout_group(group_id: str, user_id: int, start_date: date) -> list:
        """
        Duplicate all workouts in a group with the same relative spacing.

        Args:
            group_id: The workout_group_id to duplicate
            user_id: The user creating the duplicates
            start_date: The starting date for the first workout in the new group

        Returns:
            List of newly created Workout objects
        """
        # Find all workouts with this group_id, ordered by date
        source_workouts = Workout.query.filter_by(
            workout_group_id=group_id,
            user_id=user_id
        ).order_by(Workout.workout_date.asc()).all()

        if not source_workouts:
            raise ValueError("No workouts found with this group ID")

        # Calculate the relative day offsets from the first workout
        first_date = source_workouts[0].workout_date
        if isinstance(first_date, datetime):
            first_date = first_date.date()

        # Build a weekly plan format from the workouts
        weekly_plan = {'weekly_plan': []}
        specific_dates = []

        for workout in source_workouts:
            workout_date = workout.workout_date
            if isinstance(workout_date, datetime):
                workout_date = workout_date.date()

            # Calculate day offset from first workout
            day_offset = (workout_date - first_date).days
            new_date = start_date + timedelta(days=day_offset)
            specific_dates.append(new_date)

            # Serialize the workout
            plan = WorkoutService.serialize_workout_to_plan(workout)
            plan['workout_name'] = f"{plan['workout_name']} (Copy)"
            weekly_plan['weekly_plan'].append(plan)

        # Create the new workouts with the same relative spacing
        return WorkoutService.create_weekly_workouts_from_plan(
            user_id,
            weekly_plan,
            start_date,
            specific_dates=specific_dates
        )

"""
Workout Service - Handles workout CRUD operations.
"""
from datetime import date, datetime, timedelta
from typing import Optional

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
        day_spacing: int = 2
    ) -> list:
        """
        Create multiple workouts from a weekly plan.

        Args:
            user_id: The user creating the workouts
            weekly_plan: Dict with 'weekly_plan' key containing list of workout dicts
            start_date: Starting date for the first workout (defaults to today)
            day_spacing: Days between workouts (default 2)

        Returns:
            List of created Workout objects
        """
        if start_date is None:
            start_date = datetime.today().date()

        plan_list = weekly_plan.get("weekly_plan", [])
        created_workouts = []

        for idx, workout_data in enumerate(plan_list):
            workout_date = start_date + timedelta(days=idx * day_spacing)
            workout_name = workout_data.get("workout_name", f"Workout Day {idx + 1}")
            movements_list = workout_data.get("movements", [])

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

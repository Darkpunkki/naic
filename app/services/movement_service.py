"""
Movement Service - Handles movement management operations.
"""
import re

from nltk.stem import WordNetLemmatizer

from app.models import (
    db,
    Movement,
    MuscleGroup,
    MovementMuscleGroup,
    WorkoutMovement,
    Set,
    Rep,
    Weight,
)
from app.services.ai_generation_service import AIGenerationService


# Initialize lemmatizer at module level
lemmatizer = WordNetLemmatizer()


class MovementService:

    @staticmethod
    def normalize_movement_name(name: str) -> str:
        """
        Normalize movement names by standardizing case, separators, and plurals.
        Uses NLTK lemmatization for deduplication.
        """
        if not name:
            return ""

        cleaned = re.sub(r"[\s_-]+", " ", name.strip().lower())
        words = cleaned.split()
        normalized_words = []

        for word in words:
            if not word:
                continue
            try:
                lemma = lemmatizer.lemmatize(word)
            except LookupError:
                # Fallback if NLTK data isn't available during tests
                lemma = word[:-1] if word.endswith("s") and len(word) > 2 else word
            normalized_words.append(lemma)

        return "-".join(normalized_words)

    @staticmethod
    def find_or_create_movement(name: str, description: str = "") -> Movement:
        """
        Find existing movement by name or create new one.
        """
        movement = Movement.query.filter_by(movement_name=name).first()
        if not movement:
            movement = Movement(
                movement_name=name,
                movement_description=description
            )
            db.session.add(movement)
            db.session.commit()
        return movement

    @staticmethod
    def find_or_create_muscle_group(name: str) -> MuscleGroup:
        """Find existing muscle group by name or create new one."""
        mg = MuscleGroup.query.filter_by(muscle_group_name=name).first()
        if not mg:
            mg = MuscleGroup(muscle_group_name=name)
            db.session.add(mg)
            db.session.commit()
        return mg

    @staticmethod
    def link_movement_to_muscle_group(movement_id: int, muscle_group_id: int, target_percentage: int) -> MovementMuscleGroup:
        """
        Create or update link between movement and muscle group.
        """
        mmg = MovementMuscleGroup.query.filter_by(
            movement_id=movement_id,
            muscle_group_id=muscle_group_id
        ).first()

        if not mmg:
            mmg = MovementMuscleGroup(
                movement_id=movement_id,
                muscle_group_id=muscle_group_id,
                target_percentage=target_percentage
            )
            db.session.add(mmg)
            db.session.commit()

        return mmg

    @staticmethod
    def create_movement_with_muscle_groups(movement_data: dict) -> Movement:
        """
        Create a movement and its muscle group associations from AI-generated data.

        Args:
            movement_data: dict with 'name', 'description', and 'muscle_groups' list

        Returns:
            Created or existing Movement object
        """
        movement_name = movement_data.get("name", "Unknown Movement")
        description = movement_data.get("description", "")
        muscle_groups = movement_data.get("muscle_groups", [])

        # Find or create the movement
        movement = MovementService.find_or_create_movement(movement_name, description)

        # Process muscle groups
        for mg_data in muscle_groups:
            mg_name = mg_data.get("name", "")
            mg_impact = mg_data.get("impact", 0)

            if not mg_name:
                continue

            mg = MovementService.find_or_create_muscle_group(mg_name)
            MovementService.link_movement_to_muscle_group(
                movement.movement_id,
                mg.muscle_group_id,
                mg_impact
            )

        return movement

    @staticmethod
    def add_movement_to_workout(
        workout_id: int,
        movement_name: str,
        sets: int,
        reps: int,
        weight: float,
        is_bodyweight: bool = False
    ) -> WorkoutMovement:
        """
        Add a new movement to an existing workout.
        If movement doesn't exist, fetches muscle groups via AI and creates it.

        Returns the created WorkoutMovement.
        """
        # Try to find existing movement
        movement = Movement.query.filter_by(movement_name=movement_name).first()

        if not movement:
            # Get movement info from AI
            movement_json = AIGenerationService.get_movement_muscle_groups(movement_name)

            # Update weight/bodyweight from AI response if provided
            is_bodyweight = movement_json.get("is_bodyweight", is_bodyweight)
            if is_bodyweight:
                weight = 0.0
            elif "weight" in movement_json:
                weight = float(movement_json.get("weight", weight))

            # Create the movement with muscle groups
            movement_data = {
                "name": movement_json.get("movement_name", movement_name),
                "description": "",
                "muscle_groups": movement_json.get("muscle_groups", [])
            }
            movement = MovementService.create_movement_with_muscle_groups(movement_data)

        # Create the WorkoutMovement
        wm = WorkoutMovement(
            workout_id=workout_id,
            movement_id=movement.movement_id
        )
        db.session.add(wm)
        db.session.commit()

        # Create sets with reps and weights
        MovementService._create_sets_for_workout_movement(
            wm.workout_movement_id, sets, reps, weight, is_bodyweight
        )

        return wm

    @staticmethod
    def _create_sets_for_workout_movement(
        workout_movement_id: int,
        set_count: int,
        reps_per_set: int,
        weight_value: float,
        is_bodyweight: bool
    ) -> list:
        """Create sets with reps and weights for a workout movement."""
        created_sets = []

        for s_index in range(set_count):
            new_set = Set(
                workout_movement_id=workout_movement_id,
                set_order=s_index + 1
            )
            db.session.add(new_set)
            db.session.commit()

            # Create rep record
            rep_record = Rep(
                set_id=new_set.set_id,
                rep_count=reps_per_set
            )
            db.session.add(rep_record)

            # Create weight record
            w_record = Weight(
                set_id=new_set.set_id,
                weight_value=weight_value,
                is_bodyweight=is_bodyweight
            )
            db.session.add(w_record)
            db.session.commit()

            created_sets.append(new_set)

        return created_sets

    @staticmethod
    def remove_movement_from_workout(workout_movement_id: int) -> int:
        """
        Remove a movement from a workout.

        Returns the workout_id for redirect purposes.
        """
        wm = WorkoutMovement.query.get_or_404(workout_movement_id)
        workout_id = wm.workout_id

        db.session.delete(wm)
        db.session.commit()

        return workout_id

    @staticmethod
    def populate_workout_movements(workout_id: int, movements_list: list) -> list:
        """
        Create all movements for a workout from an AI-generated list.

        Args:
            workout_id: The workout to add movements to
            movements_list: List of movement dicts from AI response

        Returns:
            List of created WorkoutMovement objects
        """
        created_workout_movements = []

        for m in movements_list:
            movement_name = m.get("name", "Unknown Movement")
            set_count = m.get("sets", 3)
            reps_per_set = m.get("reps", 10)
            weight_value = float(m.get("weight", 0.0))
            is_bodyweight = bool(m.get("is_bodyweight", False))

            # Find or create the movement
            movement = MovementService.find_or_create_movement(
                movement_name,
                m.get("description", "")
            )

            # Create WorkoutMovement
            wm = WorkoutMovement(
                workout_id=workout_id,
                movement_id=movement.movement_id
            )
            db.session.add(wm)
            db.session.commit()

            # Create sets
            MovementService._create_sets_for_workout_movement(
                wm.workout_movement_id,
                set_count,
                reps_per_set,
                weight_value,
                is_bodyweight
            )

            # Process muscle groups
            for mg in m.get("muscle_groups", []):
                mg_name = mg.get("name", "")
                mg_impact = mg.get("impact", 0)

                if not mg_name:
                    continue

                mg_obj = MovementService.find_or_create_muscle_group(mg_name)
                MovementService.link_movement_to_muscle_group(
                    movement.movement_id,
                    mg_obj.muscle_group_id,
                    mg_impact
                )

            created_workout_movements.append(wm)

        return created_workout_movements

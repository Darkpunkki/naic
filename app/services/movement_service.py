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
    SetEntry,
)
from app.services.ai_generation_service import AIGenerationService


# Initialize lemmatizer at module level
lemmatizer = WordNetLemmatizer()


class MovementService:

    @staticmethod
    def normalize_movement_name(name: str) -> str:
        """
        Normalize movement names for comparison/deduplication.
        Returns lowercase, lemmatized, hyphenated form for matching.
        This is NOT the display format - use format_movement_name() for that.

        Example: "Single Leg RDL" -> "single-leg-rdl"
        """
        if not name:
            return ""

        # Remove extra whitespace, underscores, hyphens and lowercase
        cleaned = re.sub(r"[\s_-]+", " ", name.strip().lower())
        words = cleaned.split()
        normalized_words = []

        for word in words:
            if not word:
                continue
            try:
                # Lemmatize to handle plurals and verb forms
                lemma = lemmatizer.lemmatize(word)
            except LookupError:
                # Fallback if NLTK data isn't available during tests
                lemma = word[:-1] if word.endswith("s") and len(word) > 2 else word
            normalized_words.append(lemma)

        return "-".join(normalized_words)

    @staticmethod
    def format_movement_name(name: str) -> str:
        """
        Format movement name for storage/display in Title Case.
        Handles common abbreviations and special cases.

        Example: "single leg rdl" -> "Single Leg RDL"
        """
        if not name:
            return ""

        # Common abbreviations that should be uppercase
        abbreviations = {
            'rdl', 'ohp', 'db', 'bb', 'ez', 'cgbp', 'bw', 'tbdl',
            'sumo', 'rom', 'amrap', 'emom', 'rpe', 'rm'
        }

        # Clean up whitespace and separators
        cleaned = re.sub(r"[\s_-]+", " ", name.strip())
        words = cleaned.split()
        formatted_words = []

        for word in words:
            if not word:
                continue

            word_lower = word.lower()

            # Check if it's a known abbreviation
            if word_lower in abbreviations:
                formatted_words.append(word_lower.upper())
            else:
                # Title case (first letter uppercase, rest lowercase)
                formatted_words.append(word_lower.capitalize())

        return " ".join(formatted_words)

    @staticmethod
    def find_or_create_movement(name: str, description: str = "") -> Movement:
        """
        Find existing movement by name or create new one.
        Uses normalization to prevent duplicates and formats to Title Case.

        Example:
            "single leg rdl" -> finds/creates "Single Leg RDL"
            "Bench-Press" -> finds/creates "Bench Press"
        """
        # Format the input name to Title Case
        formatted_name = MovementService.format_movement_name(name)

        # Check if a similar movement already exists using normalization
        normalized_input = MovementService.normalize_movement_name(name)

        # Get all movements and check normalized forms
        all_movements = Movement.query.all()
        for mov in all_movements:
            if MovementService.normalize_movement_name(mov.movement_name) == normalized_input:
                # Found a match - return existing movement
                return mov

        # No match found - create new movement with formatted name
        movement = Movement(
            movement_name=formatted_name,
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
        Uses normalization to find similar movements.

        Returns the created WorkoutMovement.
        """
        # Format the name and check for existing movements using normalization
        formatted_name = MovementService.format_movement_name(movement_name)
        normalized_input = MovementService.normalize_movement_name(movement_name)

        # Search for existing movement using normalization
        movement = None
        all_movements = Movement.query.all()
        for mov in all_movements:
            if MovementService.normalize_movement_name(mov.movement_name) == normalized_input:
                movement = mov
                break

        if not movement:
            # Get movement info from AI using formatted name
            movement_json = AIGenerationService.get_movement_muscle_groups(formatted_name)

            # Update weight/bodyweight from AI response if provided
            is_bodyweight = movement_json.get("is_bodyweight", is_bodyweight)
            if "weight" in movement_json:
                weight = float(movement_json.get("weight", weight))

            # Create the movement with muscle groups (ensure formatted name is used)
            ai_name = movement_json.get("movement_name", formatted_name)
            final_name = MovementService.format_movement_name(ai_name)

            movement_data = {
                "name": final_name,
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

            # Create paired entry record (preferred for scoring)
            entry_record = SetEntry(
                set_id=new_set.set_id,
                entry_order=1,
                reps=reps_per_set,
                weight_value=weight_value,
                is_bodyweight=is_bodyweight
            )
            db.session.add(entry_record)
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

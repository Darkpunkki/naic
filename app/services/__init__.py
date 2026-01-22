"""
Services module for business logic.
"""
from app.services.openai_service import (
    generate_workout_plan,
    generate_weekly_workout_plan,
    generate_movement_info,
    generate_movement_instructions,
)
from app.services.ai_generation_service import AIGenerationService
from app.services.movement_service import MovementService
from app.services.workout_service import WorkoutService

__all__ = [
    # Original OpenAI service functions
    "generate_workout_plan",
    "generate_weekly_workout_plan",
    "generate_movement_info",
    "generate_movement_instructions",
    # New service classes
    "AIGenerationService",
    "MovementService",
    "WorkoutService",
]

"""
AI Generation Service - Wraps OpenAI calls with retry logic and JSON parsing.
"""
import json
import logging

from flask import current_app

from app.services.openai_service import (
    generate_workout_plan,
    generate_weekly_workout_plan,
    generate_movement_info,
    generate_movement_instructions,
)

logger = logging.getLogger(__name__)


class AIGenerationService:
    MAX_ATTEMPTS = 3

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove markdown code fences from AI response."""
        text = text.strip()
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
        # Handle case where there's still a trailing code fence
        if "```" in text:
            text = text.split("```")[0].strip()
        return text

    @staticmethod
    def _parse_ai_response(response: str) -> dict:
        """Parse JSON from AI response, handling markdown fences."""
        cleaned = AIGenerationService._strip_markdown_fences(response)
        return json.loads(cleaned)

    @staticmethod
    def generate_single_workout(sex: str, bodyweight: float, gym_experience: str, target: str) -> dict:
        """
        Generate a single workout plan with retry logic.

        Returns parsed workout plan dict or raises exception after max attempts.
        """
        last_error = None

        for attempt in range(AIGenerationService.MAX_ATTEMPTS):
            try:
                raw_response = generate_workout_plan(sex, bodyweight, gym_experience, target)
                workout_json = AIGenerationService._parse_ai_response(raw_response)
                return workout_json
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
                logger.warning(f"Raw response:\n{raw_response}\n")
                last_error = e
            except Exception as e:
                logger.error(f"Error generating workout on attempt {attempt + 1}: {e}")
                last_error = e

        raise ValueError(f"Failed to generate workout after {AIGenerationService.MAX_ATTEMPTS} attempts: {last_error}")

    @staticmethod
    def generate_weekly_workout(
        sex: str,
        bodyweight: float,
        gym_experience: str,
        target: str,
        days: int,
        duration: int
    ) -> dict:
        """
        Generate a weekly workout plan with retry logic.

        Returns parsed weekly plan dict or raises exception after max attempts.
        """
        last_error = None

        for attempt in range(AIGenerationService.MAX_ATTEMPTS):
            try:
                raw_response = generate_weekly_workout_plan(
                    sex, bodyweight, gym_experience, target, days, duration
                )
                weekly_json = AIGenerationService._parse_ai_response(raw_response)
                return weekly_json
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
                last_error = e
            except Exception as e:
                logger.error(f"Error generating weekly workout on attempt {attempt + 1}: {e}")
                last_error = e

        raise ValueError(f"Failed to generate weekly workout after {AIGenerationService.MAX_ATTEMPTS} attempts: {last_error}")

    @staticmethod
    def get_movement_muscle_groups(movement_name: str) -> dict:
        """
        Get muscle group percentages for a movement.

        Returns dict with movement_name, is_bodyweight, weight, and muscle_groups.
        """
        return generate_movement_info(movement_name)

    @staticmethod
    def get_movement_instructions(movement_name: str) -> str:
        """Get form instructions for a movement."""
        return generate_movement_instructions(movement_name)

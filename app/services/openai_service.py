import json
from typing import List
from pydantic import BaseModel, Field
from openai import OpenAI
import os

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Constants - defined once to reduce duplication
ALLOWED_MUSCLE_GROUPS = [
    "Chest", "Back", "Biceps", "Triceps", "Shoulders", "Quadriceps",
    "Hamstrings", "Calves", "Glutes", "Core", "Obliques", "Lower Back",
    "Forearms", "Neck", "Hip Flexors", "Adductors", "Abductors"
]

GOAL_GUIDANCE = {
    "muscle_growth": "Focus on hypertrophy: moderate weight, 8-12 reps, controlled tempo, adequate volume per muscle group.",
    "strength": "Focus on strength: heavier weights, lower reps (3-6), compound movements, longer rest periods.",
    "cardio": "Focus on cardio/endurance: lighter weights, higher reps (15-20+), shorter rest periods, circuit-style if appropriate.",
    "weight_loss": "Focus on fat burning: moderate weights, higher reps (12-15), supersets, minimal rest to keep heart rate elevated.",
    "general_fitness": "Focus on balanced fitness: mix of compound and isolation exercises, moderate reps (8-12), well-rounded approach."
}

GOAL_GUIDANCE_WEEKLY = {
    "muscle_growth": "Focus on hypertrophy: moderate weight, 8-12 reps, controlled tempo, adequate volume per muscle group. Structure the week to hit each major muscle group with sufficient volume.",
    "strength": "Focus on strength: heavier weights, lower reps (3-6), compound movements, longer rest periods. Prioritize progressive overload across the week.",
    "cardio": "Focus on cardio/endurance: lighter weights, higher reps (15-20+), shorter rest periods, circuit-style workouts. Include variety to maintain cardiovascular challenge.",
    "weight_loss": "Focus on fat burning: moderate weights, higher reps (12-15), supersets, minimal rest to keep heart rate elevated. Full-body sessions work well.",
    "general_fitness": "Focus on balanced fitness: mix of compound and isolation exercises, moderate reps (8-12), well-rounded approach hitting all muscle groups across the week."
}

# Pydantic models for structured outputs
class MuscleGroup(BaseModel):
    name: str = Field(description=f"Must be one of: {', '.join(ALLOWED_MUSCLE_GROUPS)}")
    impact: int = Field(description="Impact percentage (0-100). All impacts in a movement must sum to 100")

class Movement(BaseModel):
    name: str = Field(description="Name of the exercise")
    sets: int = Field(description="Number of sets", ge=1)
    reps: int = Field(description="Number of reps per set", ge=1)
    weight: float = Field(description="Weight in kg (0 if bodyweight)", ge=0)
    is_bodyweight: bool = Field(description="True if typically done with bodyweight only (push-ups, pull-ups, etc.)")
    muscle_groups: List[MuscleGroup] = Field(description="Muscle groups targeted. Impact percentages must sum to 100")

class WorkoutPlan(BaseModel):
    workout_name: str = Field(description="Summary of workout focus (e.g., 'Upper Body Strength')")
    movements: List[Movement] = Field(description="4-6 movements for the workout", min_length=4, max_length=6)

class DailyWorkout(BaseModel):
    day: str = Field(description="Day label (e.g., 'Day 1', 'Day 2')")
    workout_name: str = Field(description="Focus for this day (e.g., 'Upper Body Strength')")
    movements: List[Movement] = Field(description="4-6 movements for this workout", min_length=4, max_length=6)

class WeeklyWorkoutPlan(BaseModel):
    weekly_plan: List[DailyWorkout] = Field(description="Array of daily workouts")

class MovementInfo(BaseModel):
    movement_name: str
    is_bodyweight: bool = Field(description="True if typically done with bodyweight only")
    weight: float = Field(description="Recommended weight in kg (0 if bodyweight)", ge=0)
    muscle_groups: List[MuscleGroup] = Field(description="Muscle groups targeted. Impact percentages must sum to 100")

def generate_workout_plan(sex, weight, gymexp, target, goal="general_fitness", restrictions=""):
    """
    Generates a single workout plan using OpenAI's structured outputs.
    Returns JSON string for backward compatibility with existing code.
    """
    # Build restriction text if provided
    restriction_text = ""
    if restrictions and restrictions.strip():
        restriction_text = f"\n\nIMPORTANT - User Restrictions: {restrictions}\nYou MUST avoid any movements that conflict with these restrictions. Do not include exercises that target restricted muscle groups or could aggravate mentioned injuries."

    # Get goal guidance
    goal_guidance_text = GOAL_GUIDANCE.get(goal, GOAL_GUIDANCE["general_fitness"])

    # Shortened prompt - no need to explain format, schema enforces it
    prompt_text = f"""Generate a workout plan for:
- Sex: {sex}
- Bodyweight: {weight} kg
- Gym Experience: {gymexp}
- Goal: {goal} - {goal_guidance_text}
- Focus area: {target}{restriction_text}

Create 4-6 movements focusing on the target area with balanced muscle group coverage."""

    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",  # TODO: Update to gpt-4o or newer model before Feb 14, 2025
        messages=[
            {"role": "system", "content": "You are an expert fitness coach who creates personalized workout plans."},
            {"role": "user", "content": prompt_text}
        ],
        response_format=WorkoutPlan,
        temperature=0.7
    )

    # Convert parsed response back to JSON string for backward compatibility
    workout_plan = response.choices[0].message.parsed
    return workout_plan.model_dump_json()




def generate_movement_instructions(movement_name):
    """
    Generates detailed instructions for performing a specific movement.
    :param movement_name: Name of the movement to fetch instructions for.
    :return: Detailed instructions as a string.
    """
    prompt_text = f"""Provide concise exercise instructions for: {movement_name}

Format (use exact emojis and headers):

🎯 Setup
• [starting position]

💪 Execution
• [how to perform]

⚠️ Common Mistakes
• [what to avoid]

💡 Tips
• [quick tips]

⏱️ Rest: [recommended rest time]

Keep each bullet to one short sentence. No markdown formatting. Mobile-friendly."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # TODO: Update to gpt-4o or newer model before Feb 14, 2025
            messages=[
                {"role": "system", "content": "You are a fitness expert providing clear, concise exercise form cues."},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=300,
            temperature=0.7
        )
        instructions = response.choices[0].message.content.strip()
        return instructions
    except Exception as e:
        print(f"Error generating instructions: {e}")
        raise e


def generate_movement_info(movement_name):
    """
    Gets muscle groups and weight info for a movement using structured outputs.
    Returns a dict for backward compatibility.
    """
    prompt_text = f"""Provide exercise information for: {movement_name}

Determine:
1. Which muscle groups it targets and impact percentages (must sum to 100)
2. Whether it's typically bodyweight or uses external load
3. Recommended starting weight in kg (0 if bodyweight)"""

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",  # TODO: Update to gpt-4o or newer model before Feb 14, 2025
            messages=[
                {"role": "system", "content": "You are a fitness expert who knows exercise biomechanics and muscle activation patterns."},
                {"role": "user", "content": prompt_text}
            ],
            response_format=MovementInfo,
            temperature=0.7
        )

        movement_info = response.choices[0].message.parsed
        return movement_info.model_dump()
    except Exception as e:
        print(f"Error generating movement info: {e}")
        # Fallback if something unexpected
        return {
            "movement_name": movement_name,
            "is_bodyweight": False,
            "weight": 0,
            "muscle_groups": []
        }

def generate_weekly_workout_plan(sex, weight, gymexp, target, gym_days, session_duration, goal="general_fitness", restrictions=""):
    """
    Generates a weekly workout plan using OpenAI's structured outputs.
    Returns JSON string for backward compatibility with existing code.
    """
    # Build restriction text if provided
    restriction_text = ""
    if restrictions and restrictions.strip():
        restriction_text = f"\n\nIMPORTANT - User Restrictions: {restrictions}\nYou MUST avoid any movements that conflict with these restrictions throughout the entire weekly plan. Do not include exercises that target restricted muscle groups or could aggravate mentioned injuries."

    # Get goal guidance for weekly planning
    goal_guidance_text = GOAL_GUIDANCE_WEEKLY.get(goal, GOAL_GUIDANCE_WEEKLY["general_fitness"])

    # Shortened prompt - schema handles format enforcement
    prompt_text = f"""Generate a {gym_days}-day weekly workout plan for:
- Sex: {sex}
- Bodyweight: {weight} kg
- Gym Experience: {gymexp}
- Goal: {goal} - {goal_guidance_text}
- Focus area: {target}
- Session duration: {session_duration} minutes{restriction_text}

Create {gym_days} varied workouts with 4-6 movements each. Distribute muscle groups across the week for optimal recovery and balance."""

    response = client.beta.chat.completions.parse(
        model="gpt-5-mini",  # Using stronger model for complex weekly planning
        messages=[
            {"role": "system", "content": "You are an expert fitness coach who creates personalized weekly workout plans."},
            {"role": "user", "content": prompt_text}
        ],
        response_format=WeeklyWorkoutPlan,
        temperature=0.7
        # Note: No max_tokens needed - structured outputs are more token-efficient
    )

    # Convert parsed response back to JSON string for backward compatibility
    weekly_plan = response.choices[0].message.parsed
    return weekly_plan.model_dump_json()

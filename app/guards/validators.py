"""
Input Validators - Pydantic schemas for request validation.
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, errors: list):
        self.errors = errors
        self.message = "; ".join(errors)
        super().__init__(self.message)


# Valid enum values
VALID_GOALS = ["muscle_growth", "strength", "cardio", "weight_loss", "general_fitness"]
VALID_EXPERIENCES = ["beginner", "intermediate", "advanced", "expert"]
VALID_SEXES = ["male", "female"]


class WorkoutGenerationInput(BaseModel):
    """Validation schema for single workout generation."""

    target: str = Field(max_length=200, description="Workout focus area")
    restrictions: str = Field(default="", max_length=500, description="Injuries or limitations")
    goal: str = Field(default="general_fitness", description="Workout goal")

    @field_validator('target')
    @classmethod
    def target_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Workout target cannot be empty')
        return v.strip()

    @field_validator('goal')
    @classmethod
    def goal_valid(cls, v):
        if v and v not in VALID_GOALS:
            raise ValueError(f'Goal must be one of: {", ".join(VALID_GOALS)}')
        return v


class WeeklyWorkoutGenerationInput(BaseModel):
    """Validation schema for weekly workout generation."""

    target: str = Field(max_length=200, description="Workout focus area")
    restrictions: str = Field(default="", max_length=500, description="Injuries or limitations")
    goal: str = Field(default="general_fitness", description="Workout goal")
    gym_days: int = Field(ge=1, le=7, description="Days per week")
    session_duration: int = Field(ge=15, le=180, description="Session duration in minutes")

    @field_validator('target')
    @classmethod
    def target_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Workout target cannot be empty')
        return v.strip()

    @field_validator('goal')
    @classmethod
    def goal_valid(cls, v):
        if v and v not in VALID_GOALS:
            raise ValueError(f'Goal must be one of: {", ".join(VALID_GOALS)}')
        return v


class MovementInput(BaseModel):
    """Validation schema for movement data."""

    movement_name: str = Field(max_length=100, description="Name of the movement")
    sets: int = Field(ge=1, le=20, default=3, description="Number of sets")
    reps: int = Field(ge=1, le=100, default=10, description="Reps per set")
    weight: float = Field(ge=0, le=500, default=0, description="Weight in kg")

    @field_validator('movement_name')
    @classmethod
    def movement_name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Movement name cannot be empty')
        return v.strip()


class PendingWorkoutUpdateInput(BaseModel):
    """Validation schema for updating pending workout movements."""

    index: int = Field(ge=0, description="Movement index")
    sets: Optional[int] = Field(default=None, ge=1, le=20, description="Number of sets")
    reps: Optional[int] = Field(default=None, ge=1, le=100, description="Reps per set")
    weight: Optional[float] = Field(default=None, ge=0, le=500, description="Weight in kg")


class UserProfileInput(BaseModel):
    """Validation schema for user profile data."""

    sex: Optional[str] = Field(default=None, description="User's sex")
    bodyweight: Optional[float] = Field(default=None, ge=20, le=300, description="Bodyweight in kg")
    gym_experience: Optional[str] = Field(default=None, description="Experience level")

    @field_validator('sex')
    @classmethod
    def sex_valid(cls, v):
        if v and v not in VALID_SEXES:
            raise ValueError(f'Sex must be one of: {", ".join(VALID_SEXES)}')
        return v

    @field_validator('gym_experience')
    @classmethod
    def experience_valid(cls, v):
        if v and v not in VALID_EXPERIENCES:
            raise ValueError(f'Gym experience must be one of: {", ".join(VALID_EXPERIENCES)}')
        return v


def validate_request(schema_class, data: dict) -> dict:
    """
    Validate request data against a schema.

    Args:
        schema_class: Pydantic model class
        data: Dict of data to validate

    Returns:
        Validated data dict

    Raises:
        ValidationError: If validation fails
    """
    try:
        validated = schema_class(**data)
        return validated.model_dump()
    except Exception as e:
        # Extract error messages from pydantic ValidationError
        if hasattr(e, 'errors'):
            errors = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        else:
            errors = [str(e)]
        raise ValidationError(errors)

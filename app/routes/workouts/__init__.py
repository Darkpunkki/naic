"""Workout routes package — thin endpoints split across cohesive modules.

All submodules attach their handlers to the shared ``workouts_bp`` blueprint, so
Flask endpoint names remain ``workouts.<function_name>`` exactly as before the
split. ``app/__init__.py`` keeps importing ``workouts_bp`` from this package.
"""
from app.routes.workouts.blueprint import workouts_bp

# Importing the submodules runs their @workouts_bp.route decorators and registers
# every route on the blueprint. Order does not matter.
from app.routes.workouts import (  # noqa: E402,F401
    sessions,
    crud,
    duplication,
    movements,
    generation_single,
    generation_weekly,
)

__all__ = ["workouts_bp"]

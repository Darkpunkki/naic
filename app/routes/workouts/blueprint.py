"""Shared blueprint and helpers for the workout route modules.

All workout route submodules import ``workouts_bp`` from here and attach their
handlers to it, so Flask endpoint names stay ``workouts.<function_name>``.
"""
from datetime import datetime

from flask import Blueprint

workouts_bp = Blueprint("workouts", __name__)


def _coerce_to_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value

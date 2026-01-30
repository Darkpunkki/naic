"""
Feedback Service - Analyzes completed workout performance and generates
personalized adjustments for future workout generation.
"""
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app.models import (
    db,
    User,
    Workout,
    WorkoutMovement,
    Movement,
    SetEntry,
    UserFeedbackProfile,
    WorkoutFeedbackSummary,
    WorkoutMuscleGroupImpact,
    MuscleGroup,
)

logger = logging.getLogger(__name__)


# Goal-specific thresholds for rep decline analysis
GOAL_THRESHOLDS = {
    'strength': {
        'ideal_reps_min': 3,
        'ideal_reps_max': 6,
        'decline_tolerance': 0.60,  # Strict - expect significant fatigue
    },
    'muscle_growth': {
        'ideal_reps_min': 8,
        'ideal_reps_max': 12,
        'decline_tolerance': 0.75,  # Moderate
    },
    'cardio': {
        'ideal_reps_min': 15,
        'ideal_reps_max': 25,
        'decline_tolerance': 0.80,  # Very lenient
    },
    'weight_loss': {
        'ideal_reps_min': 12,
        'ideal_reps_max': 15,
        'decline_tolerance': 0.75,
    },
    'general_fitness': {
        'ideal_reps_min': 8,
        'ideal_reps_max': 12,
        'decline_tolerance': 0.70,
    },
}

# Paired muscle groups for imbalance detection
MUSCLE_PAIRS = [
    ('Chest', 'Back'),
    ('Biceps', 'Triceps'),
    ('Quadriceps', 'Hamstrings'),
    ('Adductors', 'Abductors'),
]


class FeedbackService:
    """
    Analyzes workout performance and generates feedback for AI prompt injection.
    """

    @staticmethod
    def analyze_rep_pattern(set_entries: List[SetEntry], goal: str = 'general_fitness') -> Dict:
        """
        Analyze rep decline across sets for a single movement.

        Args:
            set_entries: List of SetEntry objects ordered by entry_order
            goal: User's workout goal for threshold selection

        Returns:
            Dict with pattern analysis:
            {
                'pattern': 'weight_too_heavy' | 'weight_appropriate' | 'weight_too_light',
                'decline_ratio': float,
                'suggested_multiplier': float,
                'first_set_reps': int,
                'last_set_reps': int,
            }
        """
        if not set_entries or len(set_entries) < 2:
            return {
                'pattern': 'insufficient_data',
                'decline_ratio': None,
                'suggested_multiplier': 1.0,
                'first_set_reps': set_entries[0].reps if set_entries else 0,
                'last_set_reps': set_entries[-1].reps if set_entries else 0,
            }

        # Sort by entry_order to ensure correct sequence
        sorted_entries = sorted(set_entries, key=lambda e: e.entry_order)

        first_set_reps = sorted_entries[0].reps
        last_set_reps = sorted_entries[-1].reps

        # Avoid division by zero
        if first_set_reps == 0:
            return {
                'pattern': 'insufficient_data',
                'decline_ratio': None,
                'suggested_multiplier': 1.0,
                'first_set_reps': first_set_reps,
                'last_set_reps': last_set_reps,
            }

        decline_ratio = last_set_reps / first_set_reps

        # Get goal-specific thresholds
        thresholds = GOAL_THRESHOLDS.get(goal, GOAL_THRESHOLDS['general_fitness'])
        tolerance = thresholds['decline_tolerance']

        # Determine pattern and suggested multiplier
        if decline_ratio < tolerance:
            # Significant rep decline = weight too heavy
            pattern = 'weight_too_heavy'
            # Suggest 5-15% reduction based on severity
            severity = (tolerance - decline_ratio) / tolerance
            suggested_multiplier = max(0.85, 1.0 - (severity * 0.15))
        elif decline_ratio > 1.1:
            # Reps increased = weight too light
            pattern = 'weight_too_light'
            # Suggest 5-15% increase
            suggested_multiplier = min(1.15, 1.0 + ((decline_ratio - 1.0) * 0.5))
        else:
            # Within acceptable range
            pattern = 'weight_appropriate'
            suggested_multiplier = 1.0

        return {
            'pattern': pattern,
            'decline_ratio': round(decline_ratio, 3),
            'suggested_multiplier': round(suggested_multiplier, 3),
            'first_set_reps': first_set_reps,
            'last_set_reps': last_set_reps,
        }

    @staticmethod
    def analyze_completed_workout(workout: Workout, goal: str = None) -> Dict:
        """
        Analyze all movements in a completed workout.

        Args:
            workout: Completed Workout object
            goal: User's workout goal (if None, fetched from user profile)

        Returns:
            Dict with full analysis:
            {
                'movement_analyses': [...],
                'overall_quality': float,
                'recommendation': str,
            }
        """
        if not workout.is_completed:
            return {
                'error': 'Workout not completed',
                'movement_analyses': [],
                'overall_quality': 0.0,
                'recommendation': None,
            }

        # Get user's goal if not provided
        if goal is None:
            user = User.query.get(workout.user_id)
            goal = user.workout_goal if user and user.workout_goal else 'general_fitness'

        movement_analyses = []
        quality_scores = []

        for wm in workout.workout_movements:
            # Collect all set entries for this movement
            all_entries = []
            for s in wm.sets:
                all_entries.extend(s.entries)

            if not all_entries:
                continue

            # Analyze rep pattern
            analysis = FeedbackService.analyze_rep_pattern(all_entries, goal)
            analysis['movement_id'] = wm.movement_id
            analysis['movement_name'] = wm.movement.movement_name

            # Calculate quality score for this movement
            if analysis['pattern'] == 'weight_appropriate':
                quality_scores.append(1.0)
            elif analysis['pattern'] == 'weight_too_light':
                quality_scores.append(0.7)  # Not bad, just suboptimal
            elif analysis['pattern'] == 'weight_too_heavy':
                quality_scores.append(0.5)  # More problematic
            # insufficient_data doesn't contribute

            movement_analyses.append(analysis)

        # Calculate overall quality
        overall_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5

        # Generate recommendation
        too_heavy_count = sum(1 for a in movement_analyses if a['pattern'] == 'weight_too_heavy')
        too_light_count = sum(1 for a in movement_analyses if a['pattern'] == 'weight_too_light')

        if too_heavy_count > len(movement_analyses) / 2:
            recommendation = "Consider reducing weights across multiple exercises. Your rep counts declined significantly."
        elif too_light_count > len(movement_analyses) / 2:
            recommendation = "Consider increasing weights. You maintained or increased reps across sets."
        elif overall_quality >= 0.8:
            recommendation = "Good workout! Weights were appropriate for your goals."
        else:
            recommendation = "Mixed performance. Review individual movements for specific adjustments."

        return {
            'movement_analyses': movement_analyses,
            'overall_quality': round(overall_quality, 2),
            'recommendation': recommendation,
        }

    @staticmethod
    def calculate_movement_multiplier(
        user_id: int,
        movement_id: int,
        goal: str = 'general_fitness'
    ) -> Tuple[float, float]:
        """
        Calculate historical weight multiplier for a user+movement combination.

        Returns:
            Tuple of (weight_multiplier, confidence_score)
        """
        profile = UserFeedbackProfile.query.filter_by(
            user_id=user_id,
            movement_id=movement_id
        ).first()

        if not profile:
            return (1.0, 0.0)

        return (float(profile.weight_multiplier), float(profile.confidence_score))

    @staticmethod
    def analyze_muscle_group_balance(user_id: int, lookback_days: int = 30) -> List[Dict]:
        """
        Analyze muscle group balance for paired muscles over recent workouts.

        Args:
            user_id: User to analyze
            lookback_days: Number of days to look back

        Returns:
            List of imbalance findings
        """
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        # Get all completed workouts in the lookback period
        workouts = Workout.query.filter(
            Workout.user_id == user_id,
            Workout.is_completed == True,
            Workout.workout_date >= cutoff_date
        ).all()

        if not workouts:
            return []

        workout_ids = [w.workout_id for w in workouts]

        # Aggregate volume per muscle group
        muscle_volumes = {}
        impacts = WorkoutMuscleGroupImpact.query.filter(
            WorkoutMuscleGroupImpact.workout_id.in_(workout_ids)
        ).all()

        for impact in impacts:
            mg_name = impact.muscle_group.muscle_group_name
            muscle_volumes[mg_name] = muscle_volumes.get(mg_name, 0) + float(impact.total_volume)

        # Check paired muscle ratios
        imbalances = []
        for muscle_a, muscle_b in MUSCLE_PAIRS:
            vol_a = muscle_volumes.get(muscle_a, 0)
            vol_b = muscle_volumes.get(muscle_b, 0)
            total = vol_a + vol_b

            if total == 0:
                continue

            ratio_a = vol_a / total

            # Flag if ratio deviates more than 15% from 50/50
            if ratio_a > 0.65:
                imbalances.append({
                    'pair': [muscle_a, muscle_b],
                    'ratio': round(ratio_a, 2),
                    'dominant': muscle_a,
                    'recommendation': f"Consider adding more {muscle_b} exercises to balance with {muscle_a}."
                })
            elif ratio_a < 0.35:
                imbalances.append({
                    'pair': [muscle_a, muscle_b],
                    'ratio': round(ratio_a, 2),
                    'dominant': muscle_b,
                    'recommendation': f"Consider adding more {muscle_a} exercises to balance with {muscle_b}."
                })

        return imbalances

    @staticmethod
    def get_multiplier_for_movement(user_id: int, movement_name: str) -> Optional[float]:
        """
        Get the weight multiplier for a specific movement.

        Args:
            user_id: User ID
            movement_name: Name of the movement

        Returns:
            Weight multiplier (e.g., 0.9 for 10% reduction) or None if no data
        """
        # Find the movement by name
        movement = Movement.query.filter(
            Movement.movement_name.ilike(movement_name)
        ).first()

        if not movement:
            return None

        profile = UserFeedbackProfile.query.filter(
            UserFeedbackProfile.user_id == user_id,
            UserFeedbackProfile.movement_id == movement.movement_id,
            UserFeedbackProfile.confidence_score >= 0.3  # At least some confidence
        ).first()

        if not profile:
            return None

        return float(profile.weight_multiplier)

    @staticmethod
    def apply_feedback_to_plan(plan: dict, user_id: int) -> dict:
        """
        Apply weight adjustments to a generated workout plan based on user's
        feedback history. This is post-processing after AI generation.

        Args:
            plan: Workout plan dict with 'movements' list
            user_id: User ID for feedback lookup

        Returns:
            Modified plan with adjusted weights
        """
        if not plan or 'movements' not in plan:
            return plan

        adjustments_made = []

        for movement in plan['movements']:
            movement_name = movement.get('name', '')
            original_weight = movement.get('weight', 0)

            # Skip bodyweight exercises
            if movement.get('is_bodyweight', False) or original_weight == 0:
                continue

            multiplier = FeedbackService.get_multiplier_for_movement(user_id, movement_name)

            if multiplier and multiplier != 1.0:
                # Apply multiplier and round to nearest 0.5 kg
                adjusted_weight = round(original_weight * multiplier * 2) / 2
                movement['weight'] = adjusted_weight

                # Track adjustment for logging/display
                adjustments_made.append({
                    'movement': movement_name,
                    'original': original_weight,
                    'adjusted': adjusted_weight,
                    'multiplier': multiplier
                })

        # Optionally store adjustments in the plan for transparency
        if adjustments_made:
            plan['_feedback_adjustments'] = adjustments_made

        return plan

    @staticmethod
    def apply_feedback_to_weekly_plan(weekly_plan: dict, user_id: int) -> dict:
        """
        Apply weight adjustments to a generated weekly workout plan.

        Args:
            weekly_plan: Weekly plan dict with 'weekly_plan' list of workout dicts
            user_id: User ID for feedback lookup

        Returns:
            Modified weekly plan with adjusted weights
        """
        if not weekly_plan or 'weekly_plan' not in weekly_plan:
            return weekly_plan

        all_adjustments = []

        for day_plan in weekly_plan['weekly_plan']:
            if 'movements' not in day_plan:
                continue

            for movement in day_plan['movements']:
                movement_name = movement.get('name', '')
                original_weight = movement.get('weight', 0)

                # Skip bodyweight exercises
                if movement.get('is_bodyweight', False) or original_weight == 0:
                    continue

                multiplier = FeedbackService.get_multiplier_for_movement(user_id, movement_name)

                if multiplier and multiplier != 1.0:
                    adjusted_weight = round(original_weight * multiplier * 2) / 2
                    movement['weight'] = adjusted_weight

                    all_adjustments.append({
                        'day': day_plan.get('day', ''),
                        'movement': movement_name,
                        'original': original_weight,
                        'adjusted': adjusted_weight,
                        'multiplier': multiplier
                    })

        if all_adjustments:
            weekly_plan['_feedback_adjustments'] = all_adjustments

        return weekly_plan

    @staticmethod
    def process_completed_workout(workout_id: int) -> Optional[WorkoutFeedbackSummary]:
        """
        Process a completed workout and update feedback profiles.
        Called automatically after a workout is marked complete.

        Args:
            workout_id: ID of the completed workout

        Returns:
            WorkoutFeedbackSummary object or None if processing fails
        """
        workout = Workout.query.get(workout_id)
        if not workout or not workout.is_completed:
            logger.warning(f"Cannot process workout {workout_id}: not found or not completed")
            return None

        # Check if already processed
        existing_summary = WorkoutFeedbackSummary.query.filter_by(workout_id=workout_id).first()
        if existing_summary:
            logger.info(f"Workout {workout_id} already has feedback summary")
            return existing_summary

        # Get user's goal
        user = User.query.get(workout.user_id)
        goal = user.workout_goal if user and user.workout_goal else 'general_fitness'

        # Analyze the workout
        analysis = FeedbackService.analyze_completed_workout(workout, goal)

        # Create workout feedback summary
        summary = WorkoutFeedbackSummary(
            workout_id=workout_id,
            completion_quality=Decimal(str(analysis['overall_quality'])),
            overall_recommendation=analysis['recommendation'],
            movement_feedback_json=json.dumps(analysis['movement_analyses']),
        )

        # Check for imbalances
        imbalances = FeedbackService.analyze_muscle_group_balance(workout.user_id)
        if imbalances:
            summary.imbalance_feedback_json = json.dumps(imbalances)

        db.session.add(summary)

        # Update user feedback profiles for each movement
        for movement_analysis in analysis['movement_analyses']:
            if movement_analysis['pattern'] == 'insufficient_data':
                continue

            FeedbackService._update_feedback_profile(
                user_id=workout.user_id,
                movement_id=movement_analysis['movement_id'],
                pattern=movement_analysis['pattern'],
                suggested_multiplier=movement_analysis['suggested_multiplier'],
            )

        db.session.commit()
        logger.info(f"Processed feedback for workout {workout_id}: quality={analysis['overall_quality']}")

        return summary

    @staticmethod
    def _update_feedback_profile(
        user_id: int,
        movement_id: int,
        pattern: str,
        suggested_multiplier: float
    ):
        """
        Update or create a user feedback profile for a movement.
        Uses exponential moving average to smooth multiplier changes.
        """
        profile = UserFeedbackProfile.query.filter_by(
            user_id=user_id,
            movement_id=movement_id
        ).first()

        if not profile:
            # Create new profile
            profile = UserFeedbackProfile(
                user_id=user_id,
                movement_id=movement_id,
                weight_multiplier=Decimal(str(suggested_multiplier)),
                pattern_type=pattern,
                confidence_score=Decimal('0.25'),  # Low confidence for first data point
                data_points=1,
            )
            db.session.add(profile)
        else:
            # Update existing profile with exponential moving average
            # Alpha = 0.3 gives more weight to recent data
            alpha = 0.3
            current_mult = float(profile.weight_multiplier)
            new_mult = alpha * suggested_multiplier + (1 - alpha) * current_mult

            profile.weight_multiplier = Decimal(str(round(new_mult, 3)))
            profile.pattern_type = pattern
            profile.data_points += 1
            profile.last_analyzed = datetime.utcnow()

            # Increase confidence with more data points (max 1.0 at 10+ data points)
            confidence = min(1.0, profile.data_points * 0.1)
            profile.confidence_score = Decimal(str(round(confidence, 2)))

    @staticmethod
    def get_movement_feedback_history(
        user_id: int,
        movement_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get recent feedback history for a specific movement.
        Useful for displaying trends to users.

        Args:
            user_id: User ID
            movement_id: Movement ID
            limit: Max number of entries to return

        Returns:
            List of feedback entries from recent workouts
        """
        # Find workout movement instances for this user+movement
        workout_movements = (
            WorkoutMovement.query
            .join(Workout)
            .filter(
                Workout.user_id == user_id,
                Workout.is_completed == True,
                WorkoutMovement.movement_id == movement_id
            )
            .order_by(Workout.workout_date.desc())
            .limit(limit)
            .all()
        )

        history = []
        for wm in workout_movements:
            # Get entries for this workout movement
            all_entries = []
            for s in wm.sets:
                all_entries.extend(s.entries)

            if not all_entries:
                continue

            user = User.query.get(user_id)
            goal = user.workout_goal if user and user.workout_goal else 'general_fitness'

            analysis = FeedbackService.analyze_rep_pattern(all_entries, goal)
            history.append({
                'workout_date': wm.workout.workout_date.isoformat() if wm.workout.workout_date else None,
                'workout_name': wm.workout.workout_name,
                **analysis
            })

        return history

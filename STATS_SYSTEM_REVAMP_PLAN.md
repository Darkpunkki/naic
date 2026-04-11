# Stats System Revamp Plan

## Problem
The current stats experience is narrow and muscle-group focused. It shows volume totals, a basic trend line, and period-to-period deltas, but it does not surface movement-level progress, adherence to plan, personal records, or quality signals from the feedback system. It also has limited filtering and no structured way to expand.

## Goals
- Provide per-movement progress tracking with clear performance trends and personal records.
- Offer richer breakdowns by muscle group, movement type, equipment, and program block.
- Show plan adherence and quality signals (planned vs actual, skipped sets, completion quality).
- Keep stats fast by introducing precomputed summaries and sensible caching.
- Preserve backward compatibility for the current `/stats` view while the new system rolls out.

## Non-Goals (for this revamp phase)
- Full redesign of workout execution or generation flows.
- Real-time analytics across multiple users beyond current group leaderboard needs.
- Replacing the existing scoring model entirely without a migration path.

## Current State Snapshot
- Stats data is built from `WorkoutMuscleGroupImpact` and the scoring rules in `app/services/stats_service.py`.
- `/stats/data` returns muscle-group totals, trend series, and deltas for week/month/all.
- No movement-level trend, no PRs, no adherence data, and no custom date ranges.

## Product Surface (New Capabilities)
- Movement Explorer: per-movement progression charts, best sets, rep ranges, e1RM trends.
- Muscle Balance: distribution and imbalance views with adjustable windows.
- Workload & Consistency: training load by week, streaks, and weekly volume targets.
- Adherence & Quality: planned vs actual, completion quality, skipped set rate.
- Records: personal records by movement and rep range.
- Export: CSV for movement history and weekly summaries.

## Data Model Revamp
- Add `WorkoutSessionSummary`: per-workout totals like volume, sets, reps, movements, completion rate, skipped sets, and duration seconds.
- Add `WorkoutMovementStats`: per workout + movement totals like volume, tonnage, reps, sets, avg weight, max weight, e1RM, and completion rate.
- Add `MovementDailySummary`: per user + movement + date rollups for fast trend queries.
- Add `MuscleGroupDailySummary`: per user + muscle group + date rollups for fast distribution and balance charts.
- Add `PersonalRecord`: per user + movement with record type, value, reps, weight, and workout/date reference.
- Add `BodyweightLog`: time-series table for bodyweight changes to allow relative strength metrics.
- Extend `SetEntry`: optional fields like `rpe`, `rir`, `rest_seconds`, `tempo`, `is_warmup`, and `notes`.
- Extend `Movement`: optional metadata like `equipment_type`, `movement_type`, `is_unilateral`, and a primary muscle group.
- Add indexes on `workout_date`, `user_id`, `movement_id`, and summary table dates for fast filtering.

## Metric Definitions (Core)
1. Volume (impact): `effective_load * reps` using existing `StatsService` rules.
2. Tonnage: `external_weight * reps` (plus bodyweight if flagged as bodyweight movement).
3. Estimated 1RM (e1RM): use Epley `weight * (1 + reps/30)` for top set per movement.
4. Adherence: `completed_sets / planned_sets` and `actual_vs_planned_weight` ratio.
5. Consistency: workouts per week, streak length, and weekly variance.
6. Balance: muscle-pair ratios using existing `FeedbackService` pairings, plus custom views.

## Data Pipeline & Backfill
- On workout completion, compute `WorkoutSessionSummary`, `WorkoutMovementStats`, `WorkoutMuscleGroupImpact`, and update PRs.
- Use a background job or deferred task to keep completion snappy.
- Backfill historical workouts into new summary tables with a batching script similar to `scripts/backfill_workout_impacts.py`.
- Migrate legacy sets into `SetEntry` if missing using `scripts/backfill_set_entries.py` as a base.

## Rest Time Capture (Between Sets Only)
- Capture rest time as the elapsed seconds between set submissions in the UI.
- No rest time recorded between movements; only between sets within the same movement.
- Persist to `SetEntry.rest_seconds` (or a new `SetRestInterval` table if we need richer history later).
- Edge cases:
- Skipped set: do not record rest for the skipped set; the next completed set’s rest time should be measured from the last completed set.
- Back-to-back edits: if a user edits a prior set, do not overwrite rest time unless explicitly re-submitted.
- First set in a movement: rest time is `null` (no prior set).
- Timer pauses: if the user pauses the workout, rest time still reflects actual elapsed time unless we add a pause state.

## RPE Tracking
- Add optional RPE input per set in the workout UI.
- Store on `SetEntry.rpe` and exclude from stats if not provided.
- Use RPE for advanced insights (intensity vs volume, fatigue trends).

## API & Service Layer
- Introduce `app/services/stats_v2_service.py` to keep new logic isolated while reusing `StatsService` helpers.
- New endpoints:
- `GET /stats/overview` for KPI cards, totals, and headline trends.
- `GET /stats/movements` for movement list + summary metrics.
- `GET /stats/movements/<id>/series` for time series by metric.
- `GET /stats/muscles` for distribution + imbalance views.
- `GET /stats/records` for PRs and recent milestones.
- `GET /stats/adherence` for planned vs actual and completion quality.
- Keep `/stats/data` as a compatibility endpoint backed by the new summaries.

## UI/UX Revamp
- Update `templates/stats.html` into a multi-section dashboard with tabs.
- Add a Movement Explorer table with sortable metrics and quick filters.
- Add a movement detail modal or page with:
- e1RM trend, volume trend, and best set history.
- Rep range distribution and actual vs planned deltas.
- Add filters: date range, movement type, muscle group, equipment, completed only, include warmups.
- Add an export button for CSV downloads.

## Performance & Scalability
- Favor summary tables for all list and chart views.
- Keep raw set-level queries only for detail views on single movements.
- Cache recent summaries per user and invalidate on workout completion.
- Add pagination and limits to movement lists and API responses.

## Testing Plan
- Unit tests for new metric calculations and PR detection.
- Route tests for all new stats endpoints and filters.
- Backfill script test to ensure data integrity on historical workouts.
- Regression test to keep `/stats` behavior consistent.

## Rollout Plan
1. Phase 1: Data model additions + backfill scripts.
2. Phase 2: Stats v2 service + new endpoints with minimal UI wiring.
3. Phase 3: New dashboard UI + movement explorer and detail views.
4. Phase 4: Adherence, PRs, and export tooling.
5. Phase 5: Performance tuning, caching, and polish.

## Open Decisions / Questions
Resolved:
- Primary progress metric: e1RM.
- RPE/RIR tracking: yes, optional in logging UI.
- Movement stats visibility: visible in group contexts.
- Custom date ranges and goal targets: defer (not in v1).
- Store duration data: yes, capture workout start/end and set-level rest.

Remaining:
- None.

## Additional Data We Could Capture (Options)
These are not currently captured but could unlock richer stats and personalization.

Training Context:
- Perceived exertion per set (RPE) and/or reps in reserve (RIR).
- Rest time per set (seconds), and total rest per workout.
- Tempo per set (e.g., 3-1-1-0), for time-under-tension estimates.
- Warm-up and drop-set flags, to exclude or segment volume.
- Notes per set and per workout.

Execution & Quality:
- Range of motion flag (full/partial).
- Form quality check (simple scale or tags).
- Pain/discomfort flags by movement or joint.
- Failed reps or incomplete sets.

Equipment & Environment:
- Equipment used (barbell, dumbbell, machine, band).
- Grip or stance variant tags.
- Gym vs home context.

Biometrics:
- Bodyweight log at workout time.
- Sleep quality and duration (subjective or imported).
- Stress or readiness score.
- Heart rate data for cardio sessions.

Program Structure:
- Program block or phase tag (hypertrophy, strength, deload).
- Microcycle week index.
- Planned progression model (linear, undulating).

Cardio-Specific:
- Duration, distance, pace, incline, average HR.
- Zone distribution and intensity label.

Recovery:
- Soreness ratings by muscle group.
- Injury status flag.

# Workout Launcher Improvement Plan

## Problem
Today, workout selection is calendar-first (`/start_workout`), which creates friction when:
- the calendar is empty, or
- the user wants to run a specific workout now regardless of date.

## Goals
- Let users start a workout in under 2 clicks, even with an empty calendar.
- Keep calendar scheduling (drag/drop) as a secondary tool, not the only entry point.
- Preserve existing workout history and planned schedule when starting "out of schedule."

## Non-Goals (for this phase)
- No full program builder redesign.
- No major schema changes unless clearly needed.
- No changes to workout execution flow inside `active_workout`.

## Proposed UX: Workout Launcher (replace/enhance `/start_workout`)

Single page with 5 launch paths:

1. **Continue Planned for Today**
   - Shows workouts scheduled for today.
   - Primary CTA: `Start`.

2. **Start From Existing Workout**
   - Searchable list of saved workouts (recent + all).
   - CTA: `Start Now` (creates a session for today from selected workout).
   - Optional: `Schedule` (open date picker, keep current behavior).

3. **Quick Start Empty Workout**
   - CTA: `Quick Start`.
   - Creates a blank workout for today and opens active view immediately.

4. **Calendar (Current View)**
   - Keep full calendar for planning and date management.
   - Move below launch cards / collapse behind "Open Calendar."

5. **Generate New Workout**
   - Secondary launcher card.
   - Goes directly to `/generate_workout`.
   - Keeps generation discoverable when users have no saved sessions.

## Key Product Decisions

- **Start Now should always duplicate (never reuse source workout)**
  - Preserves original planned date/history.
  - Guarantees the original workout remains intact.
  - Uses existing duplication logic where possible.

- **Even if source workout is today and incomplete**
  - Still duplicate, then open the new copy.

- **If source workout is completed**
  - Start Now creates a new workout today based on it.

- **Include completed workouts in "Start From Existing"**
  - Completed workouts are valid templates for new sessions.

- **Quick start naming**
  - Default to `Quick Workout - <Day>` (example: `Quick Workout - Monday`).

- **Include Generate New Workout card in v1**
  - Add a secondary card on launcher for quick access to generation.

## Backend Design

### New/Updated Endpoints

- `GET /start_workout` (existing):
  - Return current calendar data plus:
    - `todays_workouts`
    - `recent_workouts` (last N completed/planned)
    - `all_workouts` summary for search list

- `POST /workout/<id>/start_now` (new):
  - Auth + ownership check.
  - Behavior:
    - Always duplicate source workout to today.
    - Return new workout id every time.
  - Response: `{ success: true, workout_id: X, duplicated: true }`

- `POST /workouts/quick_start` (new):
  - Creates empty workout for today with name `Quick Workout - <Day>`.
  - Response: `{ success: true, workout_id: X }`

### Service Layer

- Add in `app/services/workout_service.py`:
  - `start_workout_now(user_id, source_workout_id) -> Workout`
  - Internally reuses existing duplication/update helpers to avoid route-level duplication.

## Frontend Design

### Template
- Update `templates/start_workout.html`:
  - Add launch cards section above calendar.
  - Add searchable list (simple input + client filtering).
  - Keep calendar panel below.

### JS
- Update `static/js/start_workout_scripts.js`:
  - Add handlers:
    - `startNow(workoutId)` -> POST and redirect to `/active_workout/<id>`
    - `quickStart()` -> POST and redirect
    - in-page filtering for workout list
  - Keep existing calendar click/drag behavior.

## Data and Compatibility

- No mandatory DB migration needed for MVP.
- Works with existing `Workout`, `WorkoutMovement`, and set structures.
- Existing routes (`/new_workout`, `/duplicate_workout`, `/active_workout/<id>`) remain compatible.

## Edge Cases

- No workouts in DB: show empty state with `Quick Start` + `Generate Workout`.
- Source workout has no movements: still allow start (user can add in active view).
- Cross-user access: strict ownership check on all new start endpoints.
- Duplicate submit: idempotency guard on frontend button (disable while request pending).

## Testing Plan

### Unit Tests
- `start_workout_now`:
  - duplicates when source is today + incomplete.
  - duplicates when past/future/completed.
  - rejects non-owner.

### Route Tests
- `POST /workout/<id>/start_now` auth + ownership + response payload.
- `POST /workouts/quick_start` creates workout with today date.
- `GET /start_workout` includes new launch datasets.

### UI/Integration
- Launcher renders with:
  - today section
  - recent/all list
  - quick start button
- Existing calendar drag/drop still updates date.

## Rollout Plan

### Phase 1 (MVP)
- Add new backend start-now + quick-start endpoints.
- Add launcher cards and list to `start_workout`.
- Keep current calendar intact.

### Phase 2 (Polish)
- Add "Suggested next workout" card (based on recent history).
- Add stronger filters (goal, muscle group, duration).
- Add analytics for launcher path usage.

## Success Metrics

- Decrease time-to-start from launcher.
- Increase workouts started when calendar has no same-day entries.
- Increase repeat usage of "Start From Existing Workout."

## Decision Status

- All initial product decisions for MVP are now set.

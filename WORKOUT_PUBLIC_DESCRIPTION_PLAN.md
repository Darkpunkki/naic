# Workout Public Description Plan

## Goal
Let users add a short workout description after completing a workout. The description is public to group members and appears in the group feed.

## Scope
- Add a new optional `public_description` field on workouts.
- Collect description at completion (active workout finish + workout details “mark as completed”).
- Display description in group feed cards and group workout detail page.
- Warn users that the description is public to the group.

## Data Model
- Add `public_description` (TEXT, nullable) to `Workouts`.
- Provide a migration script to add the column for existing DBs.

## Backend
- Update `WorkoutService.complete_workout` to read, sanitize, and save `public_description`.
- Normalize: trim whitespace, treat empty as `None`, cap length (e.g., 1000 chars).

## UI
- Active workout finish panel:
  - Textarea for “Workout recap” with warning (“Visible to your group feed”).
- Workout details “Mark as Completed” action:
  - Include the same textarea + warning.
- Group feed and detail pages:
  - Render `public_description` when present, preserving line breaks.

## Tests
- Add a route test that completes a workout with a description and verifies the description appears in group feed HTML.
- Ensure empty descriptions are not rendered.

## Docs
- README: describe the public workout recap and add migration script instructions.

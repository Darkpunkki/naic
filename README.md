# Project Overview
This project is a workout-planning web app that helps users build personalized training plans, track schedules, and review movement details. OpenAI is used to generate workout plans based on user goals, preferences, and available equipment, and the app stores those plans for ongoing scheduling and review.

# Features
- User authentication and profile setup
- AI-powered workout generation via OpenAI
- Workout scheduling and calendar-ready plan creation
- Workout launcher with multiple start paths (today, existing template copy, quick start, AI generate, calendar)
- Movement/exercise details with names, descriptions, and metadata
- Active workout set editing (edit completed sets before moving on)
- Group workout feed with shared comments and inline discussion
- Database-backed persistence for users, workouts, and movements

# Project Structure
- `app.py` - Flask application entrypoint, routes, and initialization.
- `openai_service.py` - OpenAI integration for generating workout plans.
- `models.py` - Database models for users, workouts, movements, and relationships.
- `init_db.py` - Database configuration and connection setup.
- `templates/` - Jinja templates for server-rendered UI.
- `static/` - CSS, JavaScript, and other static assets.
- `scripts/seed_movements.py`, `scripts/seed_workouts.py`, `scripts/seed_workoutmovements.py` - Seed scripts for initial data.
- `scripts/populate_mock_data.py`, `scripts/clear_db.py` - Utilities for local development and testing.

# Setup
## Requirements
- Python 3.10+ (recommended)
- A running MySQL or PostgreSQL database

## Install Dependencies
```
pip install -r requirements.txt
```

## `.env` Support
- The app now auto-loads environment variables from a repo-root `.env` file when present.
- This behavior is controlled by `LOAD_DOTENV` (defaults to `true`).
- A `.env.example` template is included; copy values from it into your local `.env`.

## Environment Variables
### OpenAI
- `OPENAI_API_KEY` - API key used by `openai_service.py` to generate workout plans.

### Flask
- `FLASK_APP=app.py`
- `FLASK_ENV=development` (optional)
- `SECRET_KEY` - Flask session security key.

### Database
Set `DB_TYPE` to either:
- `mysql`
- `psql`

For MySQL:
- `MYSQL_USERNAME`
- `MYSQL_PASSWORD`
- (Optional) `MYSQL_URI` if you have a custom URI.

For PostgreSQL:
- `PSQL_USERNAME`
- `PSQL_PASSWORD`
- (Optional) `PSQL_URI` if you have a custom URI.

# Run / Usage
1. Initialize/seed data (first-time setup):
   ```
   python scripts/init_db.py
   python scripts/seed_movements.py
   python scripts/seed_workouts.py
   python scripts/seed_workoutmovements.py
   ```
2. (Optional) Add mock data for local testing:
   ```
   python scripts/populate_mock_data.py
   ```
   - Default mock login password: `TestPass123!`
3. Start the Flask server:
   ```
   flask run
   ```
4. Basic workflow:
   - Sign up or log in.
   - Open **Workout Planner** and launch workouts via:
     - Continue planned for today
     - Start from existing workout (duplicates to today, shows newest 10 first with Show More)
     - Quick Workout (creates an empty workout for today; auto-deletes if left empty)
     - Generate New Workout (AI)
     - Calendar scheduling
   - Review movement details and complete active sessions.

## Manual Launcher Test Checklist
1. Go to `/start_workout` and verify you see:
   - Continue Today
   - Start From Existing Workout
   - Quick Workout
   - Generate New Workout
   - Calendar
2. Click **Quick Workout** and verify:
   - You are redirected to `/active_workout/<id>`
   - Workout name is `Quick Workout - <current day>`
   - If you abandon without adding any movement, it should not remain in planner lists
3. In **Start From Existing Workout**, click **Start Now** on any workout and verify:
   - A new workout opens in active view
   - Original workout remains unchanged in the list/calendar
4. Use search input in **Start From Existing Workout** and verify list filtering by name/date.
5. Drag a workout in calendar to a new date and verify the change persists after refresh.

# Development Notes
- To add new movements, update seed data in `seed_movements.py` and re-run the seed script.
- Templates live in `templates/` and static assets (CSS/JS) live in `static/`.
- Use `clear_db.py` to reset local data during development.
- Stats/leaderboards now use a workout impact summary table. For existing databases, run:
  - `python scripts/backfill_set_entries.py`
  - `python scripts/backfill_workout_impacts.py`
- Group workout comments feature migration:
  - `python scripts/add_workout_comments_table.py`
  - Note: app startup runs `db.create_all()`, so missing tables are also created on deploy/startup when DB permissions allow.
- Mock data for visuals:
  - `python scripts/populate_mock_visual_data.py`

# Impact Scoring (optional overrides)
- `IMPACT_BASE_LOAD` (default 10)
- `IMPACT_EXTERNAL_WEIGHT_FACTOR` (default 1.0)
- `IMPACT_BODYWEIGHT_FACTOR` (default 0.25)
- `IMPACT_MIN_EFFECTIVE_LOAD` (default 0.0)

# Troubleshooting
- **Missing OpenAI key**: Ensure `OPENAI_API_KEY` is set in your environment.
- **Database connection errors**: Verify `DB_TYPE` and matching credentials are correct, and confirm the database service is running.
- **Flask fails to start**: Check that `FLASK_APP=app.py` is set and dependencies are installed.

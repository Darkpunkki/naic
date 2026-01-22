# Project Overview
This project is a workout-planning web app that helps users build personalized training plans, track schedules, and review movement details. OpenAI is used to generate workout plans based on user goals, preferences, and available equipment, and the app stores those plans for ongoing scheduling and review.

# Features
- User authentication and profile setup
- AI-powered workout generation via OpenAI
- Workout scheduling and calendar-ready plan creation
- Movement/exercise details with names, descriptions, and metadata
- Database-backed persistence for users, workouts, and movements

# Project Structure
- `app.py` — Flask application entrypoint, routes, and initialization.
- `openai_service.py` — OpenAI integration for generating workout plans.
- `models.py` — Database models for users, workouts, movements, and relationships.
- `init_db.py` — Database configuration and connection setup.
- `templates/` — Jinja templates for server-rendered UI.
- `static/` — CSS, JavaScript, and other static assets.
- `seed_movements.py`, `seed_workouts.py`, `seed_workoutmovements.py` — Seed scripts for initial data.
- `populate_mock_data.py`, `clear_db.py` — Utilities for local development and testing.

# Setup
## Requirements
- Python 3.10+ (recommended)
- A running MySQL or PostgreSQL database

## Install Dependencies
```
pip install -r requirements.txt
```

## Environment Variables
### OpenAI
- `OPENAI_API_KEY` — API key used by `openai_service.py` to generate workout plans.

### Flask
- `FLASK_APP=app.py`
- `FLASK_ENV=development` (optional)
- `SECRET_KEY` — Flask session security key.

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
   python init_db.py
   python seed_movements.py
   python seed_workouts.py
   python seed_workoutmovements.py
   ```
2. (Optional) Add mock data for local testing:
   ```
   python populate_mock_data.py
   ```
3. Start the Flask server:
   ```
   flask run
   ```
4. Basic workflow:
   - Sign up or log in.
   - Generate a workout plan using the AI flow.
   - Review the schedule and drill into movement details.

# Development Notes
- To add new movements, update seed data in `seed_movements.py` and re-run the seed script.
- Templates live in `templates/` and static assets (CSS/JS) live in `static/`.
- Use `clear_db.py` to reset local data during development.

# Troubleshooting
- **Missing OpenAI key**: Ensure `OPENAI_API_KEY` is set in your environment.
- **Database connection errors**: Verify `DB_TYPE` and matching credentials are correct, and confirm the database service is running.
- **Flask fails to start**: Check that `FLASK_APP=app.py` is set and dependencies are installed.

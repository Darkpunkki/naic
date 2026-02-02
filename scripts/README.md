# Scripts

Utilities for database setup and seeding.

## Usage

Scripts auto-add the repo root to `sys.path`, so imports resolve even when run directly.

```bash
python scripts/init_db.py
python scripts/seed_movements.py
python scripts/seed_workouts.py
python scripts/seed_workoutmovements.py
python scripts/populate_mock_data.py
python scripts/add_workout_comments_table.py
python scripts/clear_db.py
```

`populate_mock_data.py` now generates complete test-ready data (users, workouts, sets, groups).  
Default password for seeded mock users: `TestPass123!`

These scripts expect the same environment variables as the Flask app (see the root README for database settings).

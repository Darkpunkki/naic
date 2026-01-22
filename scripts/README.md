# Scripts

Utilities for database setup and seeding.

## Usage

Run scripts from the repo root so imports resolve correctly.

```bash
python scripts/init_db.py
python scripts/seed_movements.py
python scripts/seed_workouts.py
python scripts/seed_workoutmovements.py
python scripts/populate_mock_data.py
python scripts/clear_db.py
```

These scripts expect the same environment variables as the Flask app (see the root README for database settings).

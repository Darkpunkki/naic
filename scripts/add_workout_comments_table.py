"""
Migration script to add the WorkoutComments table.

Run once:
    python scripts/add_workout_comments_table.py
"""

import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Let migration run without manual key setup.
os.environ.setdefault("OPENAI_API_KEY", "migration-placeholder-key")
os.environ.setdefault("SECRET_KEY", "migration-placeholder-secret")

from app import create_app
from app.models import WorkoutComment, db


def migrate():
    app = create_app({"SKIP_NLTK_DOWNLOAD": True})

    with app.app_context():
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()

        if 'WorkoutComments' in tables:
            print("WorkoutComments table already exists. No migration needed.")
            return

        WorkoutComment.__table__.create(bind=db.engine, checkfirst=True)
        print("WorkoutComments table created successfully.")


if __name__ == '__main__':
    try:
        migrate()
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise

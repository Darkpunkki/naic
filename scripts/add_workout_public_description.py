"""
Migration script to add public_description column to Workouts.

Run once:
    python scripts/add_workout_public_description.py
"""
import os
import sys

from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Let migration run without manual key setup.
os.environ.setdefault("OPENAI_API_KEY", "migration-placeholder-key")
os.environ.setdefault("SECRET_KEY", "migration-placeholder-secret")

from app import create_app
from app.models import db


def migrate():
    app = create_app({"SKIP_NLTK_DOWNLOAD": True})

    with app.app_context():
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        if "Workouts" not in tables and "workouts" not in tables:
            print("Workouts table does not exist yet. Creating all tables...")
            db.create_all()
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            if "Workouts" not in tables and "workouts" not in tables:
                print("Workouts table still missing after create_all. Aborting migration.")
                return

        table_name = "Workouts" if "Workouts" in tables else "workouts"
        columns = {col["name"] for col in inspector.get_columns(table_name)}
        if "public_description" in columns:
            print("Workouts.public_description already exists. No migration needed.")
            return

        db_uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
        if "postgres" in db_uri:
            statement = f'ALTER TABLE "{table_name}" ADD COLUMN public_description TEXT'
        else:
            statement = f"ALTER TABLE {table_name} ADD COLUMN public_description TEXT"

        with db.engine.begin() as connection:
            connection.execute(text(statement))
        print("Workouts.public_description column added successfully.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise

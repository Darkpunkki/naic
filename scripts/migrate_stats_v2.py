"""
Migration script for stats v2 schema additions.

Adds new columns to existing tables and creates new summary/record tables.

Run once:
    python scripts/migrate_stats_v2.py
"""
import os
import sys

from sqlalchemy import text, create_engine, inspect
from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Load repo env without invoking full app bootstrap.
dotenv_path = os.path.join(REPO_ROOT, ".env")
if os.path.isfile(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path, override=False)

from app.models import (
    db,
    WorkoutSessionSummary,
    WorkoutMovementStats,
    MovementDailySummary,
    MuscleGroupDailySummary,
    PersonalRecord,
    BodyweightLog,
)


def _resolve_table(tables, name):
    if name in tables:
        return name
    lower = name.lower()
    if lower in tables:
        return lower
    return None


def _normalize_column_def(db_uri, column_def):
    if "postgres" not in db_uri:
        return column_def
    normalized = column_def
    if column_def.upper() == "DATETIME":
        normalized = "TIMESTAMP"
    if column_def.upper().startswith("BOOLEAN DEFAULT 0"):
        normalized = "BOOLEAN DEFAULT FALSE"
    return normalized


def _add_column(connection, db_uri, table_name, column_name, column_def, inspector):
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column_name in columns:
        return False

    column_def = _normalize_column_def(db_uri, column_def)

    if "postgres" in db_uri:
        statement = f'ALTER TABLE "{table_name}" ADD COLUMN {column_name} {column_def}'
    else:
        statement = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"

    connection.execute(text(statement))
    return True


def _build_db_uri():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    db_type = os.getenv("DB_TYPE", "mysql").lower()
    if db_type == "mysql":
        return os.getenv(
            "MYSQL_URI",
            (
                "mysql+pymysql://"
                f"{os.getenv('MYSQL_USERNAME', 'user')}:"
                f"{os.getenv('MYSQL_PASSWORD', 'password')}"
                "@localhost:3306/Workout_App"
            ),
        )
    if db_type == "psql":
        uri = os.getenv(
            "PSQL_URI",
            (
                "postgresql://"
                f"{os.getenv('PSQL_USERNAME', 'user')}:"
                f"{os.getenv('PSQL_PASSWORD', 'password')}"
                "@localhost/naic"
            ),
        )
        if "connect_timeout" not in uri:
            uri = uri + ("&" if "?" in uri else "?") + "connect_timeout=5"
        return uri
    if db_type == "sqlite":
        return os.getenv("SQLITE_URI", "sqlite:///:memory:")

    raise ValueError("Unsupported DB_TYPE. Please set it to 'mysql', 'psql', or 'sqlite'.")


def migrate():
    db_uri = _build_db_uri()
    engine = create_engine(db_uri)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if not tables:
        db.Model.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

    workouts_table = _resolve_table(tables, "Workouts")
    movements_table = _resolve_table(tables, "Movements")
    set_entries_table = _resolve_table(tables, "SetEntries")

    if not workouts_table or not movements_table or not set_entries_table:
        db.Model.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        workouts_table = _resolve_table(tables, "Workouts")
        movements_table = _resolve_table(tables, "Movements")
        set_entries_table = _resolve_table(tables, "SetEntries")

    added = []
    with engine.begin() as connection:
        if workouts_table:
            if _add_column(connection, db_uri, workouts_table, "started_at", "DATETIME", inspector):
                added.append(f"{workouts_table}.started_at")
            if _add_column(connection, db_uri, workouts_table, "completed_at", "DATETIME", inspector):
                added.append(f"{workouts_table}.completed_at")

        if movements_table:
            if _add_column(connection, db_uri, movements_table, "movement_type", "VARCHAR(50)", inspector):
                added.append(f"{movements_table}.movement_type")
            if _add_column(connection, db_uri, movements_table, "equipment_type", "VARCHAR(50)", inspector):
                added.append(f"{movements_table}.equipment_type")
            if _add_column(connection, db_uri, movements_table, "is_unilateral", "BOOLEAN DEFAULT 0", inspector):
                added.append(f"{movements_table}.is_unilateral")
            if _add_column(connection, db_uri, movements_table, "primary_muscle_group_id", "INTEGER", inspector):
                added.append(f"{movements_table}.primary_muscle_group_id")

        if set_entries_table:
            if _add_column(connection, db_uri, set_entries_table, "rest_seconds", "INTEGER", inspector):
                added.append(f"{set_entries_table}.rest_seconds")
            if _add_column(connection, db_uri, set_entries_table, "rpe", "NUMERIC(3, 1)", inspector):
                added.append(f"{set_entries_table}.rpe")
            if _add_column(connection, db_uri, set_entries_table, "rir", "NUMERIC(3, 1)", inspector):
                added.append(f"{set_entries_table}.rir")
            if _add_column(connection, db_uri, set_entries_table, "tempo", "VARCHAR(20)", inspector):
                added.append(f"{set_entries_table}.tempo")
            if _add_column(connection, db_uri, set_entries_table, "is_warmup", "BOOLEAN DEFAULT 0", inspector):
                added.append(f"{set_entries_table}.is_warmup")
            if _add_column(connection, db_uri, set_entries_table, "notes", "TEXT", inspector):
                added.append(f"{set_entries_table}.notes")

    # Create new tables for stats v2 only
    new_tables = [
        WorkoutSessionSummary.__table__,
        WorkoutMovementStats.__table__,
        MovementDailySummary.__table__,
        MuscleGroupDailySummary.__table__,
        PersonalRecord.__table__,
        BodyweightLog.__table__,
    ]
    db.Model.metadata.create_all(bind=engine, tables=new_tables)

    if added:
        print("Added columns:")
        for col in added:
            print(f"  - {col}")
    else:
        print("No column changes needed.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as exc:
        print(f"Migration failed: {exc}")
        raise

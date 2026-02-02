"""
Migration script for active workout improvements.
Adds new columns for set status, movement completion, and planned values.

Run this script to update your existing database schema.
"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from sqlalchemy import text


def run_migration():
    """Add new columns for active workout improvements."""
    app = create_app()

    with app.app_context():
        conn = db.engine.connect()

        # Detect database type
        dialect = db.engine.dialect.name

        print(f"Running migration for {dialect} database...")

        # Use quoted identifiers for case-sensitive table names
        sets_table = '"Sets"'
        workout_movement_table = '"WorkoutMovement"'
        set_entries_table = '"SetEntries"'

        try:
            # 1. Add 'status' column to Sets table
            print("Adding 'status' column to Sets table...")
            try:
                if dialect == 'sqlite':
                    conn.execute(text(
                        f"ALTER TABLE {sets_table} ADD COLUMN status VARCHAR(20) DEFAULT 'pending' NOT NULL"
                    ))
                elif dialect == 'mysql':
                    conn.execute(text(
                        f"ALTER TABLE {sets_table} ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                    ))
                else:  # PostgreSQL
                    conn.execute(text(
                        f"ALTER TABLE {sets_table} ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                    ))
                conn.commit()
                print("  - Added 'status' column to Sets")
            except Exception as e:
                if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                    print("  - 'status' column already exists, skipping")
                else:
                    raise

            # 2. Add 'is_completed' column to WorkoutMovement table
            print("Adding 'is_completed' column to WorkoutMovement table...")
            try:
                if dialect == 'sqlite':
                    conn.execute(text(
                        f"ALTER TABLE {workout_movement_table} ADD COLUMN is_completed BOOLEAN DEFAULT 0"
                    ))
                elif dialect == 'mysql':
                    conn.execute(text(
                        f"ALTER TABLE {workout_movement_table} ADD COLUMN is_completed BOOLEAN DEFAULT FALSE"
                    ))
                else:  # PostgreSQL
                    conn.execute(text(
                        f"ALTER TABLE {workout_movement_table} ADD COLUMN is_completed BOOLEAN DEFAULT FALSE"
                    ))
                conn.commit()
                print("  - Added 'is_completed' column to WorkoutMovement")
            except Exception as e:
                if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                    print("  - 'is_completed' column already exists, skipping")
                else:
                    raise

            # 3. Add 'planned_reps' column to SetEntries table
            print("Adding 'planned_reps' column to SetEntries table...")
            try:
                if dialect == 'sqlite':
                    conn.execute(text(
                        f"ALTER TABLE {set_entries_table} ADD COLUMN planned_reps INTEGER"
                    ))
                elif dialect == 'mysql':
                    conn.execute(text(
                        f"ALTER TABLE {set_entries_table} ADD COLUMN planned_reps INT"
                    ))
                else:  # PostgreSQL
                    conn.execute(text(
                        f"ALTER TABLE {set_entries_table} ADD COLUMN planned_reps INTEGER"
                    ))
                conn.commit()
                print("  - Added 'planned_reps' column to SetEntries")
            except Exception as e:
                if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                    print("  - 'planned_reps' column already exists, skipping")
                else:
                    raise

            # 4. Add 'planned_weight' column to SetEntries table
            print("Adding 'planned_weight' column to SetEntries table...")
            try:
                if dialect == 'sqlite':
                    conn.execute(text(
                        f"ALTER TABLE {set_entries_table} ADD COLUMN planned_weight DECIMAL(5,2)"
                    ))
                elif dialect == 'mysql':
                    conn.execute(text(
                        f"ALTER TABLE {set_entries_table} ADD COLUMN planned_weight DECIMAL(5,2)"
                    ))
                else:  # PostgreSQL
                    conn.execute(text(
                        f"ALTER TABLE {set_entries_table} ADD COLUMN planned_weight DECIMAL(5,2)"
                    ))
                conn.commit()
                print("  - Added 'planned_weight' column to SetEntries")
            except Exception as e:
                if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                    print("  - 'planned_weight' column already exists, skipping")
                else:
                    raise

            print("\nMigration completed successfully!")

        except Exception as e:
            print(f"\nMigration failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()


if __name__ == '__main__':
    run_migration()

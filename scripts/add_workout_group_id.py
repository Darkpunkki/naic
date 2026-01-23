"""
Migration script to add workout_group_id column to Workouts table.
Run this once after updating the model.

Usage:
    python scripts/add_workout_group_id.py
"""
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app import create_app
from app.models import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_workout_group_id_column():
    """Add workout_group_id column to Workouts table if it doesn't exist."""
    app = create_app()

    with app.app_context():
        try:
            # Check if column already exists
            db_type = os.getenv("DB_TYPE", "mysql").lower()

            if db_type == "mysql":
                result = db.session.execute(text("""
                    SELECT COUNT(*) as count
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'Workouts'
                    AND COLUMN_NAME = 'workout_group_id'
                """))
                count = result.scalar()

                if count > 0:
                    logger.info("Column 'workout_group_id' already exists in Workouts table.")
                    return

                # Add the column
                logger.info("Adding 'workout_group_id' column to Workouts table...")
                db.session.execute(text("""
                    ALTER TABLE Workouts
                    ADD COLUMN workout_group_id VARCHAR(36) NULL
                """))
                db.session.commit()
                logger.info("Successfully added 'workout_group_id' column.")

            elif db_type == "psql":
                result = db.session.execute(text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.columns
                    WHERE table_name = 'Workouts'
                    AND column_name = 'workout_group_id'
                """))
                count = result.scalar()

                if count > 0:
                    logger.info("Column 'workout_group_id' already exists in Workouts table.")
                    return

                logger.info("Adding 'workout_group_id' column to Workouts table...")
                db.session.execute(text("""
                    ALTER TABLE "Workouts"
                    ADD COLUMN workout_group_id VARCHAR(36) NULL
                """))
                db.session.commit()
                logger.info("Successfully added 'workout_group_id' column.")

            elif db_type == "sqlite":
                # SQLite doesn't have a clean way to check if column exists
                # Try to add it and catch the error if it already exists
                try:
                    logger.info("Adding 'workout_group_id' column to Workouts table...")
                    db.session.execute(text("""
                        ALTER TABLE Workouts
                        ADD COLUMN workout_group_id VARCHAR(36)
                    """))
                    db.session.commit()
                    logger.info("Successfully added 'workout_group_id' column.")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info("Column 'workout_group_id' already exists in Workouts table.")
                    else:
                        raise

            else:
                logger.error(f"Unsupported DB_TYPE: {db_type}")
                return

        except Exception as e:
            logger.error(f"Error adding column: {e}")
            db.session.rollback()
            raise


if __name__ == "__main__":
    add_workout_group_id_column()

"""
Migration script to add rate limiting columns to Users table.

Run this script if the columns don't exist:
    python scripts/add_rate_limit_columns.py
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app import create_app
from app.models import db


def add_rate_limit_columns():
    """Add rate limiting columns to Users table if they don't exist."""
    app = create_app()

    with app.app_context():
        # Check if columns already exist
        try:
            db.session.execute(text('SELECT llm_requests_hour FROM Users LIMIT 1'))
            print("Rate limit columns already exist.")
            return
        except Exception:
            pass

        # Add columns based on database type
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')

        if 'sqlite' in db_uri:
            # SQLite syntax
            statements = [
                "ALTER TABLE Users ADD COLUMN llm_requests_hour INTEGER DEFAULT 0",
                "ALTER TABLE Users ADD COLUMN llm_requests_day INTEGER DEFAULT 0",
                "ALTER TABLE Users ADD COLUMN llm_requests_reset_hour DATETIME",
                "ALTER TABLE Users ADD COLUMN llm_requests_reset_day DATETIME",
            ]
        elif 'mysql' in db_uri:
            # MySQL syntax
            statements = [
                "ALTER TABLE Users ADD COLUMN llm_requests_hour INT DEFAULT 0",
                "ALTER TABLE Users ADD COLUMN llm_requests_day INT DEFAULT 0",
                "ALTER TABLE Users ADD COLUMN llm_requests_reset_hour DATETIME",
                "ALTER TABLE Users ADD COLUMN llm_requests_reset_day DATETIME",
            ]
        else:
            # PostgreSQL syntax
            statements = [
                "ALTER TABLE Users ADD COLUMN llm_requests_hour INTEGER DEFAULT 0",
                "ALTER TABLE Users ADD COLUMN llm_requests_day INTEGER DEFAULT 0",
                "ALTER TABLE Users ADD COLUMN llm_requests_reset_hour TIMESTAMP",
                "ALTER TABLE Users ADD COLUMN llm_requests_reset_day TIMESTAMP",
            ]

        for stmt in statements:
            try:
                db.session.execute(text(stmt))
                print(f"Executed: {stmt}")
            except Exception as e:
                print(f"Warning (may already exist): {e}")

        db.session.commit()
        print("Rate limit columns migration complete.")


if __name__ == "__main__":
    add_rate_limit_columns()

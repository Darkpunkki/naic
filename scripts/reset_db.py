"""
Reset database by dropping all tables and recreating them.
USE WITH CAUTION - This will delete all data!
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import db
from sqlalchemy import text

def reset_database():
    """Drop all tables and recreate them."""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("WARNING: This will delete ALL data in the database!")
        print("=" * 60)

        try:
            # Get database engine
            engine = db.engine

            # Drop all tables
            print("\nDropping all tables...")
            db.drop_all()
            print("SUCCESS: All tables dropped successfully")

            # Recreate all tables
            print("\nCreating all tables with current schema...")
            db.create_all()
            print("SUCCESS: All tables created successfully")

            # Verify tables were created
            print("\nVerifying tables...")
            inspector = db.inspect(engine)
            tables = inspector.get_table_names()
            print(f"SUCCESS: Found {len(tables)} tables:")
            for table in sorted(tables):
                print(f"  - {table}")

            print("\nSUCCESS: Database reset completed successfully!")

        except Exception as e:
            print(f"\nERROR: Error resetting database: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    reset_database()

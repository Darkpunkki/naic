"""
Migration: Add GroupJoinRequests table
Run this script ONCE to add the new table for group join requests.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import db
from sqlalchemy import text

def migrate():
    """Add GroupJoinRequests table if it doesn't exist."""
    app = create_app()

    with app.app_context():
        # Check if table already exists
        inspector = db.inspect(db.engine)
        if 'GroupJoinRequests' in inspector.get_table_names():
            print("✓ GroupJoinRequests table already exists. No migration needed.")
            return

        print("Creating GroupJoinRequests table...")

        # Create the table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS GroupJoinRequests (
            request_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            responded_at DATETIME DEFAULT NULL,
            responded_by INTEGER DEFAULT NULL,
            FOREIGN KEY (group_id) REFERENCES UserGroups(group_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (responded_by) REFERENCES Users(user_id) ON DELETE SET NULL,
            INDEX idx_group_status (group_id, status),
            INDEX idx_user_status (user_id, status)
        );
        """

        # For PostgreSQL, use SERIAL instead of AUTO_INCREMENT
        db_type = os.getenv('DB_TYPE', 'mysql').lower()
        if db_type == 'psql':
            create_table_sql = create_table_sql.replace('AUTO_INCREMENT', '').replace('INTEGER PRIMARY KEY', 'SERIAL PRIMARY KEY')

        db.session.execute(text(create_table_sql))
        db.session.commit()

        print("✓ GroupJoinRequests table created successfully!")
        print("\nTable structure:")
        print("  - request_id: Primary key")
        print("  - group_id: Foreign key to UserGroups")
        print("  - user_id: User requesting to join")
        print("  - status: pending/accepted/rejected")
        print("  - created_at: When request was made")
        print("  - responded_at: When request was accepted/rejected")
        print("  - responded_by: Admin/owner who responded")

if __name__ == '__main__':
    print("=" * 60)
    print("Database Migration: Add GroupJoinRequests Table")
    print("=" * 60)
    print()

    try:
        migrate()
        print("\n✓ Migration completed successfully!")
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

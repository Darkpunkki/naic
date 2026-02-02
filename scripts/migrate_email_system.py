"""
Migration script to add email verification and password reset functionality.

Adds the following to User table:
- email_verified
- verification_token
- verification_token_expires
- reset_token
- reset_token_expires
- session_token
- email_notifications_enabled
- email_workout_reminders
- email_group_activity

Creates SecurityEvents table for rate limiting.

Run once:
    python scripts/migrate_email_system.py
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

from sqlalchemy import text
from app import create_app
from app.models import SecurityEvent, db


def migrate():
    app = create_app({"SKIP_NLTK_DOWNLOAD": True})

    with app.app_context():
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()

        # Detect database type
        db_type = db.engine.dialect.name
        print("=" * 60)
        print("Email System Migration")
        print(f"Database: {db_type}")
        print("=" * 60)

        # Check if Users table exists (case-insensitive check)
        users_table = None
        for table in tables:
            if table.lower() == 'users':
                users_table = table
                break

        if not users_table:
            print("❌ Users table does not exist. Run init_db first.")
            return

        print(f"Found Users table as: {users_table}")
        columns = [col['name'] for col in inspector.get_columns(users_table)]

        # Set SQL syntax based on database type
        if db_type == 'mysql':
            quote = '`'
            bool_type = 'TINYINT(1)'
        else:  # postgresql
            quote = '"'
            bool_type = 'BOOLEAN'

        # Add email verification columns
        if 'email_verified' not in columns:
            print("Adding email_verified column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN email_verified {bool_type} DEFAULT 0 NOT NULL')
            )
            db.session.commit()
            print("✓ email_verified column added")
        else:
            print("✓ email_verified column already exists")

        if 'verification_token' not in columns:
            print("Adding verification_token column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN verification_token VARCHAR(100) UNIQUE')
            )
            db.session.commit()
            print("✓ verification_token column added")
        else:
            print("✓ verification_token column already exists")

        if 'verification_token_expires' not in columns:
            print("Adding verification_token_expires column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN verification_token_expires TIMESTAMP')
            )
            db.session.commit()
            print("✓ verification_token_expires column added")
        else:
            print("✓ verification_token_expires column already exists")

        # Add password reset columns
        if 'reset_token' not in columns:
            print("Adding reset_token column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN reset_token VARCHAR(100) UNIQUE')
            )
            db.session.commit()
            print("✓ reset_token column added")
        else:
            print("✓ reset_token column already exists")

        if 'reset_token_expires' not in columns:
            print("Adding reset_token_expires column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN reset_token_expires TIMESTAMP')
            )
            db.session.commit()
            print("✓ reset_token_expires column added")
        else:
            print("✓ reset_token_expires column already exists")

        # Add session management column
        if 'session_token' not in columns:
            print("Adding session_token column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN session_token VARCHAR(100)')
            )
            db.session.commit()
            print("✓ session_token column added")
        else:
            print("✓ session_token column already exists")

        # Add email notification preference columns
        if 'email_notifications_enabled' not in columns:
            print("Adding email_notifications_enabled column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN email_notifications_enabled {bool_type} DEFAULT 1 NOT NULL')
            )
            db.session.commit()
            print("✓ email_notifications_enabled column added")
        else:
            print("✓ email_notifications_enabled column already exists")

        if 'email_workout_reminders' not in columns:
            print("Adding email_workout_reminders column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN email_workout_reminders {bool_type} DEFAULT 0 NOT NULL')
            )
            db.session.commit()
            print("✓ email_workout_reminders column added")
        else:
            print("✓ email_workout_reminders column already exists")

        if 'email_group_activity' not in columns:
            print("Adding email_group_activity column...")
            db.session.execute(
                text(f'ALTER TABLE {quote}Users{quote} ADD COLUMN email_group_activity {bool_type} DEFAULT 1 NOT NULL')
            )
            db.session.commit()
            print("✓ email_group_activity column added")
        else:
            print("✓ email_group_activity column already exists")

        # Initialize session_token for existing users
        print("\nInitializing session tokens for existing users...")
        if db_type == 'mysql':
            result = db.session.execute(
                text(f"""
                    UPDATE {quote}Users{quote}
                    SET session_token = MD5(CONCAT(RAND(), user_id))
                    WHERE session_token IS NULL
                """)
            )
        else:  # postgresql
            result = db.session.execute(
                text(f"""
                    UPDATE {quote}Users{quote}
                    SET session_token = md5(random()::text || user_id::text)
                    WHERE session_token IS NULL
                """)
            )
        db.session.commit()
        print(f"✓ Initialized session tokens for {result.rowcount} users")

        # Create SecurityEvents table
        security_table_exists = any(t.lower() == 'securityevents' for t in tables)
        if security_table_exists:
            print("\n✓ SecurityEvents table already exists")
        else:
            print("\nCreating SecurityEvents table...")
            SecurityEvent.__table__.create(bind=db.engine, checkfirst=True)
            print("✓ SecurityEvents table created")

        print("\n" + "=" * 60)
        print("✅ Email system migration completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update your .env file with email settings (MAIL_SERVER, etc.)")
        print("2. Add Flask-Mail to requirements.txt: Flask-Mail==0.9.1")
        print("3. Install: pip install Flask-Mail")
        print("4. Restart your application")
        print("\nFor production (Render):")
        print("- Add same email settings to Render environment variables")
        print("- Run this migration script via external psql connection")


if __name__ == '__main__':
    try:
        migrate()
    except Exception as exc:
        print(f"\n❌ Migration failed: {exc}")
        raise

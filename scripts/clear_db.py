from app import create_app
from app.models import db
from sqlalchemy.sql import text  # Import the text function for raw SQL

def clear_database():
    app = create_app()
    with app.app_context():
        # Disable foreign key checks to prevent constraint violations
        db.session.execute(text("PRAGMA foreign_keys = OFF"))
        db.session.commit()

        # Clear all data from each table
        for table in reversed(db.metadata.sorted_tables):  # Reverse to respect FK relationships
            db.session.execute(table.delete())
        db.session.commit()

        # Re-enable foreign key checks
        db.session.execute(text("PRAGMA foreign_keys = ON"))
        db.session.commit()

if __name__ == "__main__":
    clear_database()
    print("All data cleared, structure preserved.")

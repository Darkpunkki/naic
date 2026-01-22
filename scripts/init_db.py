import logging
import os

from sqlalchemy import text

from app.models import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db(app):
    """
    Initialize the database:
    - Configures the database connection.
    - Checks for required tables and creates them if missing.
    """
    # Dynamic database configuration
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        db_type = os.getenv("DB_TYPE", "mysql").lower()  # Default to MySQL
        if db_type == "mysql":
            app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
                "MYSQL_URI",
                (
                    "mysql+pymysql://"
                    f"{os.getenv('MYSQL_USERNAME', 'user')}:"
                    f"{os.getenv('MYSQL_PASSWORD', 'password')}"
                    "@localhost:3306/Workout_App"
                )
            )
        elif db_type == "psql":
            app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
                "PSQL_URI",
                (
                    "postgresql://"
                    f"{os.getenv('PSQL_USERNAME', 'user')}:"
                    f"{os.getenv('PSQL_PASSWORD', 'password')}"
                    "@localhost/naic"
                )
            )
        elif db_type == "sqlite":
            app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
                "SQLITE_URI",
                "sqlite:///:memory:"
            )
        else:
            logger.error("Unsupported DB_TYPE. Please set it to 'mysql', 'psql', or 'sqlite'.")
            raise ValueError("Unsupported DB_TYPE. Please set it to 'mysql', 'psql', or 'sqlite'.")

    # Database settings
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        try:
            # Test if a key table exists
            logger.info("Checking if database tables exist...")
            db.session.execute(text('SELECT 1 FROM Users LIMIT 1'))
            logger.info("Database tables are already initialized.")
        except Exception as e:
            error_message = str(e).lower()
            if ("relation" in error_message and "does not exist" in error_message) or "no such table" in error_message:
                logger.warning("Table does not exist. Initializing database...")
            else:
                logger.error("Unexpected error during table existence check: %s", e)
            try:
                db.create_all()
                logger.info("Database initialized successfully.")
            except Exception as creation_error:
                logger.error("Error initializing database: %s", creation_error)
                raise
    return db

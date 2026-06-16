import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
        # Check for DATABASE_URL first (Render and other platforms use this)
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Render uses postgres:// but SQLAlchemy needs postgresql://
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
            logger.info("Using DATABASE_URL for database connection")
        else:
            # Fall back to custom DB configuration
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

    # Schema is managed by Flask-Migrate/Alembic: migrations are applied on startup
    # (see app.create_app -> _apply_migrations_on_startup), and the test fixture
    # builds its own schema via db.create_all(). No create_all() on boot here.
    return db

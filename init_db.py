import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from models import db

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
    db_type = os.getenv("DB_TYPE", "mysql").lower()  # Default to MySQL
    if db_type == "mysql":
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
            "MYSQL_URI", 
            f"mysql+pymysql://{os.getenv('MYSQL_USERNAME', 'user')}:{os.getenv('MYSQL_PASSWORD', 'password')}@localhost:3306/Workout_App"
        )
    elif db_type == "psql":
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
            "PSQL_URI", 
            f"postgresql://{os.getenv('PSQL_USERNAME', 'user')}:{os.getenv('PSQL_PASSWORD', 'password')}@localhost/naic"
        )
    else:
        logger.error("Unsupported DB_TYPE. Please set it to 'mysql' or 'psql'.")
        raise ValueError("Unsupported DB_TYPE. Please set it to 'mysql' or 'psql'.")

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
            if "relation" in str(e) and "does not exist" in str(e):
                logger.warning("Table does not exist. Initializing database...")
            else:
                logger.error("Unexpected error during table existence check: %s", e)
            try:
                db.create_all()
                logger.info("Database initialized successfully.")
            except Exception as creation_error:
                logger.error("Error initializing database: %s", creation_error)
                raise

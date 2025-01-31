from flask import Flask
import logging
import nltk
from nltk.stem import WordNetLemmatizer
import os
from init_db import init_db
from routes.auth import auth_bp
from routes.workouts import workout_bp
from routes.leaderboard import leaderboard_bp
from routes.main import main_bp
from routes.user import user_bp
from routes.stats import stats_bp

nltk.download('wordnet')
nltk.download('omw-1.4')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")  # Use a secure secret key in production

# Initialize database
if app.config.get("ENV", "development") == "development":
    logger.info("Running in development mode.")
db = init_db(app)

lemmatizer = WordNetLemmatizer()

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(user_bp)
app.register_blueprint(workout_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(stats_bp)

# Remove the now-moved routes
# Routes for user authentication


if __name__ == "__main__":
    app.run(debug=True)

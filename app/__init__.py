import logging
import os

import nltk
from flask import Flask

from app.models import db
from app.routes.auth import auth_bp
from app.routes.workouts import workouts_bp
from app.routes.leaderboard import leaderboard_bp
from app.routes.main import main_bp
from app.routes.stats import stats_bp
from app.routes.user import user_bp
from app.routes.groups import groups_bp

from scripts.init_db import init_db


def create_app(test_config=None):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")
    if test_config:
        app.config.update(test_config)

    app.config.setdefault("IMPACT_BASE_LOAD", float(os.getenv("IMPACT_BASE_LOAD", 10)))
    app.config.setdefault("IMPACT_EXTERNAL_WEIGHT_FACTOR", float(os.getenv("IMPACT_EXTERNAL_WEIGHT_FACTOR", 1.0)))
    app.config.setdefault("IMPACT_BODYWEIGHT_FACTOR", float(os.getenv("IMPACT_BODYWEIGHT_FACTOR", 0.25)))
    app.config.setdefault("IMPACT_MIN_EFFECTIVE_LOAD", float(os.getenv("IMPACT_MIN_EFFECTIVE_LOAD", 0.0)))

    if app.config.get("ENV", "development") == "development":
        logger.info("Running in development mode.")

    if not app.config.get("TESTING") and not app.config.get("SKIP_NLTK_DOWNLOAD"):
        nltk.download("wordnet")
        nltk.download("omw-1.4")

    init_db(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(workouts_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(groups_bp)



    return app


__all__ = ["create_app", "db"]

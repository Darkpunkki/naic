import pytest

from app import create_app, db


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "SKIP_NLTK_DOWNLOAD": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SECRET_KEY": "test-secret",
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()

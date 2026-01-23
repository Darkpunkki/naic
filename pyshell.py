from app import create_app
from app.models import db

"""
Initialize the database by creating all tables.
"""
app = create_app()
with app.app_context():
      db.create_all()
      print("successfully created database tables.")
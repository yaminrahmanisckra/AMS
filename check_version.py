from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    try:
        result = db.session.execute(text("SELECT version_num FROM alembic_version"))
        for row in result:
            print(f"Current revision: {row[0]}")
    except Exception as e:
        print(f"Error: {e}")

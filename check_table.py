from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    try:
        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='alumni_survey_response';"))
        if result.fetchone():
            print("Table alumni_survey_response exists.")
        else:
            print("Table alumni_survey_response DOES NOT exist.")
    except Exception as e:
        print(f"Error: {e}")

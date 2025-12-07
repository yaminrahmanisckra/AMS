"""Script to create course_outline table directly in SQLite database"""
from app import create_app
from extensions import db
from blueprints.class_management.models import CourseOutline

app = create_app()

with app.app_context():
    # Create the table if it doesn't exist
    db.create_all()
    print("Course outline table created successfully!")






















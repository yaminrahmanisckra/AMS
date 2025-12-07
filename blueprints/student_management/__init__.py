from flask import Blueprint

student_management_bp = Blueprint('student_management', __name__, template_folder='templates')

from . import routes, models  # Import models so they're registered with SQLAlchemy


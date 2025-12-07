from flask import Blueprint

course_management_bp = Blueprint('course_management', __name__, template_folder='templates')

from . import routes, models  # Import models so they're registered with SQLAlchemy


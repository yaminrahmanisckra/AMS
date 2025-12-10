from flask import Blueprint

academic_calendar_bp = Blueprint('academic_calendar', __name__, template_folder='templates')

from . import routes



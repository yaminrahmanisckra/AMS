from flask import Blueprint

leave_application_bp = Blueprint('leave_application', __name__, template_folder='templates')

from . import routes


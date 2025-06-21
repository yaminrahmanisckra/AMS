from flask import Blueprint

routine_management_bp = Blueprint('routine_management', __name__, url_prefix='/routine_management')

from . import routes

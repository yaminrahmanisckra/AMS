from flask import Blueprint

curriculator_bp = Blueprint('curriculator', __name__, template_folder='templates')

from . import routes, models  # noqa: E402, F401

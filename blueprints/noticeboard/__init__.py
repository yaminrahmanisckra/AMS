from flask import Blueprint

noticeboard_bp = Blueprint('noticeboard', __name__, template_folder='templates')

from . import routes  # noqa: E402,F401
from . import models  # noqa: E402,F401

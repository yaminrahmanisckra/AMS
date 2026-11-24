from flask import Blueprint

site_backup_bp = Blueprint('site_backup', __name__, template_folder='templates')

from . import routes  # noqa: E402,F401

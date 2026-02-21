from flask import Blueprint

self_assessment_bp = Blueprint('self_assessment', __name__, template_folder='templates')

from . import routes

from flask import Blueprint

admission_exam_bp = Blueprint('admission_exam', __name__, template_folder='templates')

from . import routes

from flask import Blueprint

class_management_bp = Blueprint('class_management', __name__, 
                               url_prefix='/class-management',
                               template_folder='templates',
                               static_folder='static')

from . import routes 
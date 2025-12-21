from flask import Blueprint

class_management_bp = Blueprint('class_management', __name__, 
                               url_prefix='/class-management',
                               template_folder='templates',
                               static_folder='static')

# Import routes - this will import the module but heavy imports inside routes are lazy
# Routes are registered via decorators, so importing the module is sufficient
from . import routes 
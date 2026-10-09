from flask import Blueprint

written_assignment_bp = Blueprint(
    'written_assignment',
    __name__,
    template_folder='templates',
)

from . import models  # noqa: E402, F401
from . import routes  # noqa: E402, F401

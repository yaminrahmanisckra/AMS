from flask import Blueprint

mock_trial_simulator_bp = Blueprint(
    'mock_trial_simulator',
    __name__,
    template_folder='templates',
)

from . import models  # noqa: E402, F401
from .pdf import pdf_rich_text  # noqa: E402
from . import routes  # noqa: E402, F401

mock_trial_simulator_bp.add_app_template_filter(pdf_rich_text, 'mts_pdf')

from flask import Blueprint

admission_exam_bp = Blueprint('admission_exam', __name__, template_folder='templates')

from . import routes  # noqa: E402,F401

# Gateway webhooks cannot send Flask CSRF tokens; exempt only this endpoint.
try:
    from extensions import csrf
    csrf.exempt(routes.candidate_pay_webhook)
except Exception:
    pass

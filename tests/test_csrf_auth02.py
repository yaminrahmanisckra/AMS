"""AUTH-02 leftovers: logout is POST; admission public POSTs are not CSRF-exempt."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admission_public_posts_are_not_csrf_exempt():
    text = (ROOT / 'blueprints/admission_exam/routes.py').read_text(encoding='utf-8')
    assert '@csrf.exempt' not in text


def test_admission_public_forms_include_csrf_token():
    apply_form = (ROOT / 'blueprints/admission_exam/templates/admission_exam/apply_form.html').read_text(encoding='utf-8')
    login = (ROOT / 'blueprints/admission_exam/templates/admission_exam/candidate_login.html').read_text(encoding='utf-8')
    dash = (ROOT / 'blueprints/admission_exam/templates/admission_exam/candidate_dashboard.html').read_text(encoding='utf-8')
    assert 'csrf_token()' in apply_form
    assert 'csrf_token()' in login
    assert dash.count('csrf_token()') >= 5

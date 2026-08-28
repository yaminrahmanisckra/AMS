"""Smoke tests: operational window isolation."""
import pytest
from werkzeug.exceptions import NotFound

from blueprints.class_management.models import Session
from tests.conftest import login_client
from utils.window_utils import get_or_404_for_window, query_for_window


def test_query_for_window_returns_only_active_window(app, class_session_w1, class_session_w2, windows):
    with app.test_request_context():
        from flask import session as flask_session

        flask_session['active_window_id'] = windows['w1_id']
        flask_session['active_role'] = 'teacher'

        rows = query_for_window(Session).all()
        ids = {row.id for row in rows}
        assert class_session_w1['session_id'] in ids
        assert class_session_w2['session_id'] not in ids


def test_get_or_404_for_window_blocks_other_window(app, class_session_w2, windows):
    with app.test_request_context():
        from flask import session as flask_session

        flask_session['active_window_id'] = windows['w1_id']
        flask_session['active_role'] = 'teacher'

        with pytest.raises(NotFound):
            get_or_404_for_window(Session, class_session_w2['session_id'])


def test_assessment_autosave_404_for_other_window(
    client, teacher_user, class_session_w2, windows,
):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    session_id = class_session_w2['session_id']
    student_id = class_session_w2['student_id']
    rv = client.post(
        f'/class-management/assessment/{session_id}/auto-save',
        json={f'assessment1_{student_id}': '12'},
    )
    assert rv.status_code in (404, 500)
    if rv.is_json:
        assert rv.get_json().get('success') is not True


def test_null_window_id_visible_in_window_1_only(app, teacher_user, windows):
    """Legacy NULL window_id rows belong to Window 1."""
    from extensions import db

    with app.app_context():
        legacy = Session(
            year='Fourth',
            term='First',
            academic_session='2024-25',
            window_id=None,
            course_code='LEGACY',
            course_name='Legacy Session',
            teacher_id=teacher_user['teacher_id'],
            course_type='theory',
            category='ug',
        )
        db.session.add(legacy)
        db.session.commit()
        legacy_id = legacy.id

    with app.test_request_context():
        from flask import session as flask_session

        flask_session['active_window_id'] = windows['w1_id']
        flask_session['active_role'] = 'teacher'
        assert get_or_404_for_window(Session, legacy_id).id == legacy_id

        flask_session['active_window_id'] = windows['w2_id']
        with pytest.raises(NotFound):
            get_or_404_for_window(Session, legacy_id)

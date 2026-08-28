"""Smoke tests: assessment marks auto-save (preserve on blank)."""
from blueprints.class_management.models import ClassStudent
from extensions import db
from tests.conftest import login_client


def test_autosave_stores_mark(app, client, teacher_user, class_session_w1, windows):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    session_id = class_session_w1['session_id']
    student_id = class_session_w1['student_id']
    key = f'assessment1_{student_id}'

    rv = client.post(
        f'/class-management/assessment/{session_id}/auto-save',
        json={key: '8'},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True

    with app.app_context():
        row = db.session.get(ClassStudent, student_id)
        assert row.assessment1 == 8.0


def test_autosave_blank_does_not_wipe_saved_mark(app, client, teacher_user, class_session_w1, windows):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    session_id = class_session_w1['session_id']
    student_id = class_session_w1['student_id']
    key = f'assessment1_{student_id}'

    client.post(f'/class-management/assessment/{session_id}/auto-save', json={key: '9'})
    rv = client.post(f'/class-management/assessment/{session_id}/auto-save', json={key: ''})
    assert rv.status_code == 200
    assert rv.get_json()['success'] is True

    with app.app_context():
        row = db.session.get(ClassStudent, student_id)
        assert row.assessment1 == 9.0


def test_autosave_requires_login(client, class_session_w1):
    session_id = class_session_w1['session_id']
    student_id = class_session_w1['student_id']
    rv = client.post(
        f'/class-management/assessment/{session_id}/auto-save',
        json={f'assessment1_{student_id}': '10'},
    )
    assert rv.status_code in (302, 401, 403)

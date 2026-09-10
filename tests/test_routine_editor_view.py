"""Routine editors can open a saved routine in view-only mode."""
from blueprints.class_management.models import Teacher
from blueprints.course_management.models import DutyAssignment
from blueprints.routine_management.models import SavedRoutine
from extensions import db
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User


def _seed_routine_editor(app, windows, *, revealed=False):
    with app.app_context():
        teacher = Teacher(name='Routine Maker Test', short_name='RMT', institute='Test Institute')
        db.session.add(teacher)
        db.session.flush()
        user = User(
            username='routinemaker1',
            email='routinemaker1@test.example',
            full_name='Routine Maker',
            role='teacher',
            teacher_id=teacher.id,
        )
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.add(DutyAssignment(
            duty_type='routine_maker',
            assigned_teacher_id=teacher.id,
            status='active',
            window_id=windows['w1_id'],
        ))
        routine = SavedRoutine(
            year='2026',
            name='2026',
            is_revealed=revealed,
            window_id=windows['w1_id'],
            created_by_id=user.id,
        )
        db.session.add(routine)
        db.session.commit()
        return {'username': user.username, 'routine_id': routine.id}


def test_dashboard_shows_view_before_edit(client, app, windows):
    ids = _seed_routine_editor(app, windows)
    login_client(client, ids['username'], role='teacher', window_id=windows['w1_id'])
    rv = client.get('/routine-management/')
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    view_at = body.find('view-routine-btn')
    edit_at = body.find('load-routine-btn')
    assert view_at != -1
    assert edit_at != -1
    assert view_at < edit_at
    assert f'/routine-management/view_routine?saved_routine_id={ids["routine_id"]}' in body
    assert '</i> View' in body


def test_editor_view_is_read_only(client, app, windows):
    ids = _seed_routine_editor(app, windows)
    login_client(client, ids['username'], role='teacher', window_id=windows['w1_id'])
    rv = client.get(f'/routine-management/view_routine?saved_routine_id={ids["routine_id"]}')
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    assert 'View only' in body
    assert 'canEdit: false' in body
    assert 'id="btn-save"' not in body
    assert 'href="/routine-management/"' in body


def test_editor_edit_still_allows_save(client, app, windows):
    ids = _seed_routine_editor(app, windows)
    login_client(client, ids['username'], role='teacher', window_id=windows['w1_id'])
    rv = client.get(f'/routine-management/generate_routine?saved_routine_id={ids["routine_id"]}')
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    assert 'canEdit: true' in body
    assert 'id="btn-save"' in body
    assert 'View only' not in body

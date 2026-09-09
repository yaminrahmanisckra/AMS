"""AUTHZ-07: Teacher identity is users.teacher_id only (no name spoofing)."""
from types import SimpleNamespace

from blueprints.class_management.models import Session, Teacher
from extensions import db
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User
from utils.ownership import resolve_caller_teacher, user_owns_class_session


def test_resolve_caller_teacher_uses_teacher_id_only(app):
    with app.app_context():
        t_real = Teacher(name='Real Teacher', short_name='REAL', institute='I')
        t_fake = Teacher(name='Spoof Target', short_name='SPOOF', institute='I')
        db.session.add_all([t_real, t_fake])
        db.session.flush()

        user = SimpleNamespace(teacher_id=t_real.id, full_name='Spoof Target')
        assert resolve_caller_teacher(user).id == t_real.id

        user_unlinked = SimpleNamespace(teacher_id=None, full_name='Spoof Target')
        assert resolve_caller_teacher(user_unlinked) is None


def test_name_match_does_not_grant_session_ownership(app, windows):
    with app.app_context():
        owner = Teacher(name='Owner Teacher', short_name='OWN', institute='I')
        other = Teacher(name='Other Teacher', short_name='OTH', institute='I')
        db.session.add_all([owner, other])
        db.session.flush()

        sess = Session(
            year='Second',
            term='First',
            academic_session='2024-25',
            window_id=windows['w1_id'],
            course_code='LAW 2101',
            course_name='Course',
            teacher_id=owner.id,
            course_type='theory',
            category='ug',
        )
        db.session.add(sess)
        db.session.commit()

        spoof = SimpleNamespace(teacher_id=None, full_name='Owner Teacher')
        assert not user_owns_class_session(spoof, sess)

        linked = SimpleNamespace(teacher_id=other.id, full_name='Owner Teacher')
        assert not user_owns_class_session(linked, sess)

        real = SimpleNamespace(teacher_id=owner.id, full_name='Anything')
        assert user_owns_class_session(real, sess)


def test_non_admin_cannot_rename_profile(client, app, windows, teacher_user):
    login_client(client, teacher_user['username'], role='teacher', window_id=windows['w1_id'])
    rv = client.post(
        '/profile',
        data={
            'full_name': 'Hijacked External Name',
            'email': 'teacher1@test.example',
            'theme': 'default',
        },
        follow_redirects=True,
    )
    assert rv.status_code == 200
    assert b'cannot be changed' in rv.data or b'managed by the institution' in rv.data
    with app.app_context():
        user = User.query.get(teacher_user['user_id'])
        assert user.full_name == 'Test Teacher'


def test_teacher_without_teacher_id_cannot_open_class_index(client, app, windows):
    with app.app_context():
        orphan = Teacher(name='Orphan Roster', short_name='ORPH', institute='I')
        db.session.add(orphan)
        db.session.flush()
        user = User(
            username='nolink',
            email='nolink@test.example',
            full_name='Orphan Roster',
            role='teacher',
            teacher_id=None,
        )
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()

    login_client(client, 'nolink', role='teacher', window_id=windows['w1_id'])
    rv = client.get('/class-management/', follow_redirects=False)
    assert rv.status_code in (302, 303, 403)

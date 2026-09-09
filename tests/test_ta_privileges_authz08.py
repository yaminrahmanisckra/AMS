"""AUTHZ-08: Teaching Assistants only get attendance/marks on assigned sessions."""
from blueprints.class_management.models import Session, Teacher
from blueprints.course_management.models import DutyAssignment
from blueprints.student_management.models import Student as StudentMgmt
from extensions import db
from role_utils import has_teacher_privileges, is_teaching_assistant
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User
from utils.ownership import (
    duty_matches_class_session,
    user_can_operate_class_session,
    user_is_ta_for_session,
)


def _seed_ta_and_sessions(app, windows):
    with app.app_context():
        teacher = Teacher(name='Course Owner', short_name='COWN', institute='Test Institute')
        db.session.add(teacher)
        db.session.flush()

        student = StudentMgmt(student_id='TA001', name='TA Student')
        db.session.add(student)
        db.session.flush()

        user = User(
            username='TA001',
            email='ta001@test.example',
            full_name='TA Student',
            role='student,teaching_assistant',
        )
        user.set_password(TEST_PASSWORD)
        db.session.add(user)

        owned = Session(
            year='Second',
            term='First',
            academic_session='2024-25',
            window_id=windows['w1_id'],
            course_code='LAW 2101',
            course_name='Assigned Course',
            teacher_id=teacher.id,
            course_type='theory',
            category='ug',
        )
        other = Session(
            year='Second',
            term='First',
            academic_session='2024-25',
            window_id=windows['w1_id'],
            course_code='LAW 2103',
            course_name='Other Course',
            teacher_id=teacher.id,
            course_type='theory',
            category='ug',
        )
        db.session.add_all([owned, other])
        db.session.flush()

        duty = DutyAssignment(
            duty_type='teaching_assistant',
            student_id=student.id,
            course_code='LAW 2101',
            academic_session='2024-25',
            year='Second',
            term='First',
            status='active',
            window_id=windows['w1_id'],
        )
        db.session.add(duty)
        db.session.commit()
        return {
            'owned_id': owned.id,
            'other_id': other.id,
            'username': 'TA001',
            'duty_id': duty.id,
            'student_id': student.id,
        }


def test_ta_role_is_not_full_teacher():
    user = User(username='x', email='x@t.e', full_name='X', role='teaching_assistant')
    user.active_role = 'teaching_assistant'
    assert is_teaching_assistant(user)
    assert not has_teacher_privileges(user)


def test_legacy_unscoped_duty_never_matches_session(app, windows):
    with app.app_context():
        teacher = Teacher(name='T', short_name='T1', institute='I')
        db.session.add(teacher)
        db.session.flush()
        student = StudentMgmt(student_id='LEGACY1', name='Legacy TA')
        db.session.add(student)
        db.session.flush()
        sess = Session(
            year='Second',
            term='First',
            academic_session='2024-25',
            window_id=windows['w1_id'],
            course_code='LAW 2101',
            course_name='Course',
            teacher_id=teacher.id,
            course_type='theory',
            category='ug',
        )
        duty = DutyAssignment(
            duty_type='teaching_assistant',
            student_id=student.id,
            status='active',
            window_id=windows['w1_id'],
        )
        db.session.add_all([sess, duty])
        db.session.commit()
        assert not duty_matches_class_session(duty, sess)


def test_ta_can_take_attendance_on_assigned_session(client, app, windows):
    data = _seed_ta_and_sessions(app, windows)
    login_client(client, data['username'], role='teaching_assistant', window_id=windows['w1_id'])
    rv = client.get(f"/class-management/take_attendance/{data['owned_id']}")
    assert rv.status_code == 200


def test_ta_cannot_take_attendance_on_other_session(client, app, windows):
    data = _seed_ta_and_sessions(app, windows)
    login_client(client, data['username'], role='teaching_assistant', window_id=windows['w1_id'])
    rv = client.get(f"/class-management/take_attendance/{data['other_id']}", follow_redirects=False)
    assert rv.status_code in (302, 303, 403)


def test_ta_can_open_assessment_on_assigned_session(client, app, windows):
    data = _seed_ta_and_sessions(app, windows)
    login_client(client, data['username'], role='teaching_assistant', window_id=windows['w1_id'])
    rv = client.get(f"/class-management/assessment/{data['owned_id']}")
    assert rv.status_code == 200


def test_ta_cannot_create_session(client, app, windows):
    data = _seed_ta_and_sessions(app, windows)
    login_client(client, data['username'], role='teaching_assistant', window_id=windows['w1_id'])
    rv = client.post(
        '/class-management/create_session',
        data={},
        follow_redirects=False,
    )
    assert rv.status_code in (302, 303, 403)


def test_ta_cannot_compose_notice(client, app, windows):
    data = _seed_ta_and_sessions(app, windows)
    login_client(client, data['username'], role='teaching_assistant', window_id=windows['w1_id'])
    rv = client.get('/noticeboard/create', follow_redirects=False)
    assert rv.status_code in (302, 303, 403)


def test_ta_cannot_open_course_assessment_invite(client, app, windows):
    data = _seed_ta_and_sessions(app, windows)
    login_client(client, data['username'], role='teaching_assistant', window_id=windows['w1_id'])
    rv = client.get(
        f"/class-management/evaluation/{data['owned_id']}/course-assessment",
        follow_redirects=False,
    )
    assert rv.status_code in (302, 303, 403)


def test_helper_operate_matches_assigned_only(app, windows):
    data = _seed_ta_and_sessions(app, windows)
    with app.app_context():
        user = User.query.filter_by(username=data['username']).first()
        user.active_role = 'teaching_assistant'
        owned = Session.query.get(data['owned_id'])
        other = Session.query.get(data['other_id'])
        assert user_is_ta_for_session(user, owned)
        assert user_can_operate_class_session(user, owned)
        assert not user_is_ta_for_session(user, other)
        assert not user_can_operate_class_session(user, other)

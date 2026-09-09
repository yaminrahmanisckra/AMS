"""AUTHZ-05: Result Management tabulators cannot touch another session."""
from blueprints.course_management.models import DutyAssignment
from blueprints.result_management.models import RSession, RStudent, RSubject
from extensions import db
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User


def _seed_tabulator_sessions(app, teacher_user, windows):
    with app.app_context():
        assignment = DutyAssignment(
            duty_type='tabulator',
            assigned_teacher_id=teacher_user['teacher_id'],
            academic_session='2024-25',
            year='Fourth',
            term='First',
            status='active',
            window_id=windows['w1_id'],
        )
        allowed = RSession(
            name='2024-25',
            year='Fourth',
            term='First',
            window_id=windows['w1_id'],
        )
        other = RSession(
            name='2024-25',
            year='Third',
            term='First',
            window_id=windows['w1_id'],
        )
        db.session.add_all([assignment, allowed, other])
        db.session.flush()
        allowed_student = RStudent(
            student_id='R001',
            name='Allowed Student',
            session_id=allowed.id,
        )
        other_student = RStudent(
            student_id='R900',
            name='Other Session Student',
            session_id=other.id,
        )
        other_subject = RSubject(
            code='LAW 3101',
            name='Other Course',
            credit=3,
            session_id=other.id,
            subject_type='Theory',
        )
        db.session.add_all([allowed_student, other_student, other_subject])
        db.session.commit()
        return {
            'allowed_session_id': allowed.id,
            'allowed_student_id': allowed_student.id,
            'other_session_id': other.id,
            'other_student_id': other_student.id,
            'other_subject_id': other_subject.id,
        }


def test_tabulator_cannot_edit_other_session_student(client, app, teacher_user, windows):
    ids = _seed_tabulator_sessions(app, teacher_user, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    rv = client.post(
        f'/result-management/edit_student/{ids["other_student_id"]}',
        data={'student_id': 'HACKED', 'name': 'Hacked', 'year': '', 'discipline': '', 'school': ''},
        follow_redirects=False,
    )
    assert rv.status_code == 403
    with app.app_context():
        student = RStudent.query.get(ids['other_student_id'])
        assert student.student_id == 'R900'
        assert student.name == 'Other Session Student'


def test_tabulator_cannot_delete_other_session_student(client, app, teacher_user, windows):
    ids = _seed_tabulator_sessions(app, teacher_user, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    rv = client.post(
        f'/result-management/delete_student/{ids["other_student_id"]}',
        follow_redirects=False,
    )
    assert rv.status_code == 403
    with app.app_context():
        assert RStudent.query.get(ids['other_student_id']) is not None


def test_tabulator_cannot_delete_other_session_subject(client, app, teacher_user, windows):
    ids = _seed_tabulator_sessions(app, teacher_user, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    rv = client.post(
        f'/result-management/delete_subject/{ids["other_subject_id"]}',
        follow_redirects=False,
    )
    assert rv.status_code == 403
    with app.app_context():
        assert RSubject.query.get(ids['other_subject_id']) is not None


def test_tabulator_cannot_download_other_session(client, app, teacher_user, windows):
    ids = _seed_tabulator_sessions(app, teacher_user, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    course_pdf = client.get(
        f'/result-management/download/course_result/{ids["other_session_id"]}/{ids["other_subject_id"]}',
        follow_redirects=False,
    )
    assert course_pdf.status_code == 403

    student_pdf = client.get(
        f'/result-management/download/student_result/{ids["other_session_id"]}/{ids["other_student_id"]}',
        follow_redirects=False,
    )
    assert student_pdf.status_code == 403

    bulk = client.get(
        f'/result-management/download/all_student_results/{ids["other_session_id"]}',
        follow_redirects=False,
    )
    assert bulk.status_code == 403


def test_tabulator_can_open_assigned_session_student(client, app, teacher_user, windows):
    ids = _seed_tabulator_sessions(app, teacher_user, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    rv = client.get(
        f'/result-management/edit_student/{ids["allowed_student_id"]}',
        follow_redirects=False,
    )
    assert rv.status_code == 200


def test_head_can_access_any_result_session(client, app, teacher_user, windows):
    ids = _seed_tabulator_sessions(app, teacher_user, windows)
    with app.app_context():
        head = User(
            username='headrm',
            email='headrm@test.example',
            full_name='Result Head',
            role='head',
        )
        head.set_password(TEST_PASSWORD)
        db.session.add(head)
        db.session.commit()

    login_client(client, 'headrm', role='head', window_id=windows['w1_id'])
    rv = client.get(
        f'/result-management/edit_student/{ids["other_student_id"]}',
        follow_redirects=False,
    )
    assert rv.status_code == 200

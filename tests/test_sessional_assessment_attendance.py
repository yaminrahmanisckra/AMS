"""Sessional assessment shows attendance marks read-only."""
from blueprints.class_management.models import ClassStudent, Session
from blueprints.student_management.models import Student as StudentMgmt
from extensions import db
from tests.conftest import login_client


def _seed_sessional_session(app, teacher_user, window_id, *, manual_marks=8):
    with app.app_context():
        db.session.add(StudentMgmt(student_id='S9001', name='Sessional Student'))
        sess = Session(
            year='Fourth',
            term='Second',
            academic_session='2024-25',
            window_id=window_id,
            course_code='LAW 4208',
            course_name='Conveyancing Sessional',
            teacher_id=teacher_user['teacher_id'],
            course_type='sessional',
            category='ug',
        )
        db.session.add(sess)
        db.session.flush()
        student = ClassStudent(
            student_id='S9001',
            name='Sessional Student',
            session_id=sess.id,
            teacher_id=teacher_user['teacher_id'],
            sessional_report=50,
            sessional_viva=22,
            attendance_marks_manual=manual_marks,
        )
        db.session.add(student)
        db.session.commit()
        return {'session_id': sess.id, 'student_id': student.id}


def test_sessional_assessment_shows_readonly_attendance(
    app, client, teacher_user, windows,
):
    seeded = _seed_sessional_session(app, teacher_user, windows['w1_id'], manual_marks=8)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.get(f"/class-management/assessment/{seeded['session_id']}")
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Attendance (10)' in html
    assert 'Total (Sessional: 100)' in html
    assert 'as-col-attendance' in html
    assert 'name="attendance_' not in html
    assert 'data-attendance-mark="8' in html
    assert 'sessional_total_' in html
    assert 'data-sessional-total="80' in html


def test_sessional_assessment_post_does_not_change_attendance_marks(
    app, client, teacher_user, windows,
):
    seeded = _seed_sessional_session(app, teacher_user, windows['w1_id'], manual_marks=9)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    student_pk = seeded['student_id']
    rv = client.post(
        f"/class-management/assessment/{seeded['session_id']}",
        data={
            f'sessional_report_{student_pk}': '55',
            f'sessional_viva_{student_pk}': '24',
            f'attendance_{student_pk}': '1',
        },
        follow_redirects=False,
    )
    assert rv.status_code in (302, 303)
    with app.app_context():
        row = db.session.get(ClassStudent, student_pk)
        assert row.attendance_marks_manual == 9
        assert row.sessional_report == 55
        assert row.sessional_viva == 24


def test_theory_assessment_has_no_attendance_marks_column(
    app, client, teacher_user, class_session_w1, windows,
):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.get(f"/class-management/assessment/{class_session_w1['session_id']}")
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Attendance (10)' not in html
    assert 'data-label="Attendance"' not in html

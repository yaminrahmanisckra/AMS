"""AUTHZ-03/04/10: Class Management mutations require session ownership."""
from blueprints.class_management.models import ClassStudent, Session, Teacher
from extensions import db
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User


def _make_teacher(username, full_name, short_name):
    teacher = Teacher(name=full_name, short_name=short_name, institute='Test Institute')
    db.session.add(teacher)
    db.session.flush()
    user = User(
        username=username,
        email=f'{username}@test.example',
        full_name=full_name,
        role='teacher',
        teacher_id=teacher.id,
    )
    user.set_password(TEST_PASSWORD)
    db.session.add(user)
    db.session.commit()
    return {'teacher_id': teacher.id, 'username': username}


def _make_session(teacher_id, window_id, *, course_code='LAW 2101', student_id='S900'):
    sess = Session(
        year='Second',
        term='First',
        academic_session='2024-25',
        window_id=window_id,
        course_code=course_code,
        course_name='Owned Course',
        teacher_id=teacher_id,
        course_type='theory',
        category='ug',
    )
    db.session.add(sess)
    db.session.flush()
    student = ClassStudent(
        student_id=student_id,
        name='Original Name',
        session_id=sess.id,
        teacher_id=teacher_id,
    )
    db.session.add(student)
    db.session.commit()
    return {'session_id': sess.id, 'student_id': student.id}


def _other_teacher_session(app, windows):
    with app.app_context():
        other = _make_teacher('teacher2', 'Other Teacher', 'OT')
        owned = _make_session(other['teacher_id'], windows['w1_id'])
        return other, owned


def test_other_teacher_cannot_edit_student(client, app, teacher_user, windows):
    _, owned = _other_teacher_session(app, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    rv = client.post(
        f'/class-management/edit_student/{owned["student_id"]}',
        data={'student_id': 'HACKED', 'name': 'Hacked Name'},
        follow_redirects=False,
    )
    assert rv.status_code in (302, 303)
    assert '/class-management' in (rv.headers.get('Location') or '')
    assert f'/students/{owned["session_id"]}' not in (rv.headers.get('Location') or '')

    with app.app_context():
        student = ClassStudent.query.get(owned['student_id'])
        assert student.student_id == 'S900'
        assert student.name == 'Original Name'


def test_other_teacher_cannot_delete_student(client, app, teacher_user, windows):
    _, owned = _other_teacher_session(app, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    rv = client.post(
        f'/class-management/delete_student/{owned["student_id"]}',
        follow_redirects=False,
    )
    assert rv.status_code in (302, 303)
    assert f'/students/{owned["session_id"]}' not in (rv.headers.get('Location') or '')

    with app.app_context():
        assert ClassStudent.query.get(owned['student_id']) is not None


def test_owner_can_edit_own_student(client, app, teacher_user, class_session_w1, windows):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    student_id = class_session_w1['student_id']
    session_id = class_session_w1['session_id']

    rv = client.post(
        f'/class-management/edit_student/{student_id}',
        data={'student_id': 'S001', 'name': 'Updated Name'},
        follow_redirects=False,
    )
    assert rv.status_code in (302, 303)
    assert f'/students/{session_id}' in (rv.headers.get('Location') or '')

    with app.app_context():
        student = ClassStudent.query.get(student_id)
        assert student.name == 'Updated Name'


def test_other_teacher_cannot_list_or_add_students(client, app, teacher_user, windows):
    _, owned = _other_teacher_session(app, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    listing = client.get(f'/class-management/students/{owned["session_id"]}', follow_redirects=False)
    assert listing.status_code in (302, 303)

    add = client.post(
        f'/class-management/add_student/{owned["session_id"]}',
        json={'student_ids': [1]},
        headers={'Content-Type': 'application/json'},
    )
    assert add.status_code == 403
    body = add.get_json()
    assert body.get('success') is False
    assert body.get('error') == 'unauthorized'


def test_other_teacher_cannot_archive_or_edit_session(client, app, teacher_user, windows):
    _, owned = _other_teacher_session(app, windows)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    archive = client.post(
        f'/class-management/archive_session/{owned["session_id"]}',
        follow_redirects=False,
    )
    assert archive.status_code in (302, 303)

    with app.app_context():
        assert ClassStudent.query.get(owned['student_id']) is not None
        assert Session.query.get(owned['session_id']).archived is not True

    edit = client.get(
        f'/class-management/edit_session/{owned["session_id"]}',
        follow_redirects=False,
    )
    assert edit.status_code in (302, 303)

    invite = client.get(
        f'/class-management/evaluation/{owned["session_id"]}/course-assessment',
        follow_redirects=False,
    )
    assert invite.status_code in (302, 303)


def test_head_can_access_other_teacher_session(client, app, windows):
    _, owned = _other_teacher_session(app, windows)
    with app.app_context():
        head = User(
            username='head1',
            email='head1@test.example',
            full_name='Head User',
            role='head',
        )
        head.set_password(TEST_PASSWORD)
        db.session.add(head)
        db.session.commit()

    login_client(client, 'head1', role='head', window_id=windows['w1_id'])
    rv = client.get(f'/class-management/students/{owned["session_id"]}', follow_redirects=False)
    assert rv.status_code == 200


def test_edit_student_other_window_is_404(
    client, teacher_user, class_session_w2, windows,
):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/edit_student/{class_session_w2["student_id"]}',
        data={'student_id': 'S002', 'name': 'Cross Window'},
        follow_redirects=False,
    )
    assert rv.status_code == 404
    with client.application.app_context():
        student = ClassStudent.query.get(class_session_w2['student_id'])
        assert student.name == 'Student Two'

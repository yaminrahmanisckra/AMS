"""Mobile sign-in and the teacher/student class-routine feed."""
from datetime import datetime, timedelta, timezone

from blueprints.class_management.models import Teacher
from blueprints.course_management.models import Course, OperationalWindow, StudentCourseRegistration
from blueprints.routine_management.models import AssignedCourse, Routine, SavedRoutine
from extensions import csrf, db
from tests.conftest import TEST_PASSWORD
from user_models import User
from utils.dashboard_settings import StudentDashboardCard, ensure_student_dashboard_cards


def _user(username, role, *, teacher_id=None, full_name=None, must_change_password=False):
    user = User(
        username=username,
        email=f'{username}@test.example',
        full_name=full_name or username,
        role=role,
        teacher_id=teacher_id,
        must_change_password=must_change_password,
    )
    user.set_password(TEST_PASSWORD)
    db.session.add(user)
    return user


def _routine(window_id, *, revealed=True, year='2026', name='2026'):
    saved = SavedRoutine(
        year=year,
        name=name,
        is_revealed=revealed,
        window_id=window_id,
    )
    db.session.add(saved)
    db.session.flush()
    return saved


def _slot(saved, **kwargs):
    payload = {
        'day': 'Sunday',
        'time_slot': '09:10 AM - 10:00 AM',
        'room_number': '201',
        'course_code': 'LAW 2101',
        'teacher_short_name': 'TT',
        'part': 'Full',
        'saved_routine_id': saved.id,
        'window_id': saved.window_id,
    }
    payload.update(kwargs)
    row = Routine(**payload)
    db.session.add(row)
    return row


def _login(client, username, password=TEST_PASSWORD):
    return client.post('/api/mobile/v1/login', json={
        'username': username,
        'password': password,
    })


def _token(client, username):
    response = _login(client, username)
    assert response.status_code == 200, response.get_json()
    return response.get_json()['token']


def _routine_feed(client, token):
    return client.get(
        '/api/mobile/v1/routine',
        headers={'Authorization': f'Bearer {token}'},
    )


def test_mobile_blueprint_is_csrf_exempt():
    assert 'mobile_api' in csrf._exempt_blueprints


def test_login_rejects_bad_password_and_skips_browser_session(client, teacher_user):
    response = _login(client, teacher_user['username'], password='wrong-password')
    assert response.status_code == 401
    assert response.get_json()['error'] == 'invalid_login'
    with client.session_transaction() as sess:
        assert '_user_id' not in sess


def test_login_returns_token_without_browser_session(client, teacher_user):
    response = _login(client, teacher_user['username'])
    body = response.get_json()
    assert response.status_code == 200
    assert body['ok'] is True
    assert body['user']['role'] == 'teacher'
    assert body['user']['name'] == 'Test Teacher'
    assert 'password' not in body['token']
    with client.session_transaction() as sess:
        assert '_user_id' not in sess

    me = client.get(
        '/api/mobile/v1/me',
        headers={'Authorization': f'Bearer {body["token"]}'},
    )
    assert me.status_code == 200
    assert me.get_json()['user']['username'] == teacher_user['username']


def test_mobile_token_opens_the_real_website(client, app, teacher_user):
    token = _token(client, teacher_user['username'])
    opened = client.get(
        '/api/mobile/v1/web-session',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert opened.status_code == 302
    assert opened.location
    with client.session_transaction() as sess:
        assert '_user_id' in sess
        assert sess['active_role'] == 'teacher'

    with app.test_client() as fresh:
        denied = fresh.get('/api/mobile/v1/web-session')
    assert denied.status_code == 401


def test_website_login_feeds_the_phone_widget(client, teacher_user, windows):
    from tests.conftest import login_client

    login_client(client, teacher_user['username'], role='teacher', window_id=windows['w1_id'])
    response = client.get('/api/mobile/v1/routine-web')
    assert response.status_code == 200
    body = response.get_json()
    assert body['ok'] is True
    assert 'classes' in body
    assert 'widget' in body


def test_web_session_cannot_read_mobile_routine(client, teacher_user, windows):
    from tests.conftest import login_client

    login_client(client, teacher_user['username'], role='teacher', window_id=windows['w1_id'])
    response = client.get('/api/mobile/v1/routine')
    assert response.status_code == 401


def test_officer_and_password_change_are_rejected(client, app):
    with app.app_context():
        _user('office1', 'officer', full_name='Office User')
        _user('freshstudent', 'student', full_name='New Student', must_change_password=True)
        db.session.commit()

    officer = _login(client, 'office1')
    assert officer.status_code == 403
    assert officer.get_json()['error'] == 'role_not_supported'

    fresh = _login(client, 'freshstudent')
    assert fresh.status_code == 403
    assert fresh.get_json()['error'] == 'password_change_required'
    assert 'token' not in fresh.get_json()


def test_password_change_invalidates_token(client, teacher_user, app):
    token = _token(client, teacher_user['username'])
    with app.app_context():
        user = User.query.filter_by(username=teacher_user['username']).one()
        user.set_password('a-different-password')
        db.session.commit()

    stale = _routine_feed(client, token)
    assert stale.status_code == 401

    rebound = _login(client, teacher_user['username'], password='a-different-password')
    assert rebound.status_code == 200


def test_teacher_sees_only_own_published_classes(client, app, windows, monkeypatch):
    sunday = datetime(2026, 10, 18, 8, 0, tzinfo=timezone(timedelta(hours=6)))
    monkeypatch.setattr('blueprints.mobile_api.routine_feed.bd_now', lambda: sunday)

    with app.app_context():
        teacher = Teacher(name='Routine Teacher', short_name='TT', call_sign='TT', institute='Test')
        other = Teacher(name='Other Teacher', short_name='ZZ', institute='Test')
        db.session.add_all([teacher, other])
        db.session.flush()
        _user('routineteacher', 'teacher', teacher_id=teacher.id, full_name='Routine Teacher')
        course = Course(
            course_code='LAW 2101',
            course_name='Legal History',
            credit=3,
            course_type='Theory',
        )
        unassigned = Course(
            course_code='LAW 2103',
            course_name='Contract',
            credit=3,
            course_type='Theory',
        )
        blank = Course(
            course_code='LAW 2199',
            course_name='Unassigned',
            credit=3,
            course_type='Theory',
        )
        db.session.add_all([course, unassigned, blank])
        db.session.flush()
        db.session.add(AssignedCourse(
            teacher_id=teacher.id,
            course_id=unassigned.id,
            part='Full',
            window_id=windows['w1_id'],
        ))

        published = _routine(windows['w1_id'])
        _slot(published, teacher_id=teacher.id, teacher_short_name='TT', room_number='201')
        _slot(
            published,
            time_slot='02:00 PM - 02:50 PM',
            room_number='202',
            course_code='LAW 2102',
            teacher_id=None,
            teacher_short_name='ZZ/TT',
            part='Shared',
            is_shared=True,
        )
        _slot(
            published,
            time_slot='10:10 AM - 11:00 AM',
            room_number='301',
            course_code='LAW 2104',
            teacher_id=other.id,
            teacher_short_name='ZZ',
        )
        _slot(
            published,
            day='Monday',
            time_slot='11:10 AM - 12:00 PM',
            room_number='203',
            course_code='LAW 2103',
            teacher_id=None,
            teacher_short_name='',
            part='Full',
        )
        _slot(
            published,
            day='Monday',
            time_slot='12:10 PM - 01:00 PM',
            room_number='204',
            course_code='LAW 2199',
            teacher_id=None,
            teacher_short_name='',
            part='Full',
        )
        hidden = _routine(windows['w1_id'], revealed=False, year='2025', name='Draft')
        _slot(hidden, teacher_id=teacher.id, course_code='LAW 9999', room_number='109')

        closed = OperationalWindow.query.get(windows['w2_id'])
        closed.is_active = False
        other_window = _routine(windows['w2_id'], year='2024', name='Closed')
        _slot(other_window, teacher_id=teacher.id, course_code='LAW 8888', room_number='401')
        db.session.commit()

    token = _token(client, 'routineteacher')
    response = _routine_feed(client, token)
    assert response.status_code == 200
    body = response.get_json()
    codes = [item['course_code'] for item in body['classes']]
    assert codes == ['LAW 2101', 'LAW 2102', 'LAW 2103']
    assert body['classes'][0]['course_name'] == 'Legal History'
    assert body['classes'][0]['start'] == '09:10'
    assert body['classes'][1]['start'] == '14:00'
    assert body['classes'][1]['time_compact'] == '2:00–2:50 PM'
    assert [item['course_code'] for item in body['today_classes']] == ['LAW 2101', 'LAW 2102']
    assert [line['course_code'] for line in body['widget']['lines']] == ['LAW 2101', 'LAW 2102']
    assert body['widget']['more_count'] == 0
    assert body['notice'] is None
    assert all(item['routine_name'] != 'Draft' for item in body['classes'])
    assert 'LAW 8888' not in codes
    assert 'LAW 2199' not in codes


def test_student_sees_only_registered_courses_in_that_window(client, app, windows, monkeypatch):
    sunday = datetime(2026, 10, 18, 8, 0, tzinfo=timezone(timedelta(hours=6)))
    monkeypatch.setattr('blueprints.mobile_api.routine_feed.bd_now', lambda: sunday)

    with app.app_context():
        from blueprints.student_management.models import Student

        student = Student(student_id='S100', name='Student Hundred', batch='28')
        db.session.add(student)
        db.session.flush()
        _user('S100', 'student', full_name='Student Hundred')
        db.session.add(Course(
            course_code='LAW 2101',
            course_name='Catalog Name',
            credit=3,
            course_type='Theory',
        ))
        published = _routine(windows['w1_id'])
        _slot(published, course_code='0421 28 LAW 2101', teacher_short_name='TT', teacher_id=None)
        _slot(
            published,
            time_slot='10:10 AM - 11:00 AM',
            room_number='202',
            course_code='LAW 2104',
            teacher_short_name='ZZ',
            teacher_id=None,
        )
        other = _routine(windows['w2_id'], year='2025', name='Other window')
        _slot(other, course_code='LAW 2101', room_number='501', teacher_short_name='TT', teacher_id=None)
        db.session.add(StudentCourseRegistration(
            student_id=student.id,
            academic_session='2024-25',
            year='Second',
            term='First',
            course_code='LAW 2101',
            course_name='Legal History',
            credit=3,
            course_type='Theory',
            status='finalized',
            window_id=windows['w1_id'],
        ))
        db.session.add(StudentCourseRegistration(
            student_id=student.id,
            academic_session='2024-25',
            year='Second',
            term='First',
            course_code='LAW 2104',
            course_name='Archived Course',
            credit=3,
            course_type='Theory',
            status='archived',
            window_id=windows['w1_id'],
        ))
        db.session.commit()

    token = _token(client, 'S100')
    response = _routine_feed(client, token)
    assert response.status_code == 200
    body = response.get_json()
    assert [item['course_code'] for item in body['classes']] == ['0421 28 LAW 2101']
    assert body['classes'][0]['course_name'] == 'Legal History'
    assert body['classes'][0]['window_id'] == windows['w1_id']
    assert body['widget']['lines'][0]['detail'] == '201 · TT'
    assert body['viewer'] == 'student'


def test_student_routine_respects_dashboard_switch(client, app, windows):
    with app.app_context():
        from blueprints.student_management.models import Student

        db.session.add(Student(student_id='S200', name='Student Two Hundred'))
        _user('S200', 'student', full_name='Student Two Hundred')
        ensure_student_dashboard_cards()
        card = StudentDashboardCard.query.filter_by(card_key='class_routine').one()
        card.is_enabled = False
        db.session.commit()

    token = _token(client, 'S200')
    response = _routine_feed(client, token)
    assert response.status_code == 403
    assert response.get_json()['error'] == 'feature_disabled'

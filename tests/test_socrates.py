"""Socrates AI debate companion: assignment, prompt limit, access control, marking."""
import json
from datetime import datetime
from unittest.mock import patch

from blueprints.class_management.models import (
    SocratesAssignment,
    SocratesConversation,
    SocratesGroup,
    SocratesGroupMember,
    SocratesMessage,
)
from extensions import db
from tests.conftest import TEST_PASSWORD, login_client
from utils.ai.socrates import score_out_of_ten


def test_scores_round_to_half_marks_out_of_ten():
    assert score_out_of_ten(1.23) == 1.0
    assert score_out_of_ten(6.67) == 6.5
    assert score_out_of_ten(7.25) == 7.5
    assert score_out_of_ten(8.5) == 8.5
    assert score_out_of_ten(10.4) == 10.0
    assert score_out_of_ten(-1) == 0.0
    assert score_out_of_ten('7') == 7.0
    assert score_out_of_ten('') is None


def _ensure_student_user(username='S001', name='Student One'):
    from user_models import User

    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(
            username=username,
            email=f'{username.lower()}@test.example',
            full_name=name,
            role='student',
        )
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
    return user


def _seed_assignment(session_id, teacher_id, mode='individual', prompt_limit=15):
    assignment = SocratesAssignment(
        session_id=session_id,
        teacher_id=teacher_id,
        topic='Capital punishment should be abolished in Bangladesh',
        instructions='Argue your position with authority.',
        mode=mode,
        prompt_limit=prompt_limit,
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment.id


def _fake_evaluation():
    return {
        'scores': {'logic': 7, 'evidence': 6, 'rebuttal': 7, 'clarity': 8, 'engagement': 7},
        'strengths': ['Consistent position'],
        'weaknesses': ['Limited use of case law'],
        'summary': 'The student maintained a coherent abolitionist position.',
        'suggested_score': 7.0,
    }


def test_socrates_home_lists_teacher_courses(app, client, teacher_user, class_session_w1, windows):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.get('/class-management/socrates')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'LAW 4103' in html
    assert 'Set Up' in html

    with app.app_context():
        _seed_assignment(class_session_w1['session_id'], teacher_user['teacher_id'])

    rv = client.get('/class-management/socrates')
    html = rv.get_data(as_text=True)
    assert 'Capital punishment should be abolished in Bangladesh' in html
    assert 'Manage' in html


def test_socrates_is_dashboard_card_not_on_evaluation(app, client, teacher_user, class_session_w1, windows):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    dash = client.get('/')
    assert dash.status_code == 200
    dash_html = dash.get_data(as_text=True)
    assert '>Socrates<' in dash_html
    assert '/class-management/socrates' in dash_html
    assert 'images/socrates.png' in dash_html

    evaluation = client.get(f'/class-management/evaluation/{session_id}')
    assert evaluation.status_code == 200
    evaluation_html = evaluation.get_data(as_text=True)
    assert 'Socrates' not in evaluation_html
    assert 'Student Feedback' in evaluation_html


def test_student_dashboard_shows_socrates_card(app, client, windows):
    with app.app_context():
        _ensure_student_user()

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    rv = client.get('/student/dashboard')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert '>Socrates<' in html
    assert '/class-management/student/socrates' in html
    assert 'images/socrates.png' in html


def test_student_chat_page_shows_live_composer(app, client, teacher_user, class_session_w1, windows):
    session_id = class_session_w1['session_id']
    with app.app_context():
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'])
        assignment = SocratesAssignment.query.get(assignment_id)
        assignment.deadline = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        db.session.commit()
        _ensure_student_user()

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    rv = client.get(f'/class-management/student/socrates/{assignment_id}')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'name="message"' in html
    assert 'লাইভ চ্যাট' in html
    assert 'socrates.png' in html
    assert 'in progress' not in html.lower()


@patch('utils.ai.socrates.generate_socrates_reply')
def test_student_form_post_sends_argument(mock_reply, app, client, teacher_user, class_session_w1, windows):
    mock_reply.return_value = 'But what is your authority for that claim?'
    session_id = class_session_w1['session_id']
    with app.app_context():
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'])
        _ensure_student_user()

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        data={'message': 'The death penalty violates the right to life.'},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'The death penalty violates the right to life.' in html
    assert 'But what is your authority for that claim?' in html


def test_teacher_creates_assignment_and_group(app, client, teacher_user, class_session_w1, windows):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])

    rv = client.post(
        f'/class-management/socrates/{session_id}',
        data={
            'action': 'create',
            'topic': 'AI should be allowed in exams',
            'mode': 'group',
            'prompt_limit': '5',
        },
        follow_redirects=True,
    )
    assert rv.status_code == 200

    with app.app_context():
        assignment = SocratesAssignment.query.filter_by(session_id=session_id).first()
        assert assignment is not None
        assert assignment.mode == 'group'
        assert assignment.prompt_limit == 5
        assignment_id = assignment.id

    rv = client.post(
        f'/class-management/socrates/{session_id}/assignment/{assignment_id}',
        data={'action': 'create_group', 'group_name': 'Group A', 'member_ids': ['S001']},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    with app.app_context():
        group = SocratesGroup.query.filter_by(assignment_id=assignment_id).first()
        assert group is not None
        assert [m.student_id for m in group.members] == ['S001']


def test_teacher_can_create_multiple_assignments(app, client, teacher_user, class_session_w1, windows):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    for topic in ('First debate topic', 'Second debate topic'):
        rv = client.post(
            f'/class-management/socrates/{session_id}',
            data={'action': 'create', 'topic': topic, 'mode': 'individual', 'prompt_limit': '10'},
            follow_redirects=True,
        )
        assert rv.status_code == 200
        assert topic in rv.get_data(as_text=True)

    with app.app_context():
        topics = [
            row.topic
            for row in SocratesAssignment.query.filter_by(session_id=session_id)
            .order_by(SocratesAssignment.id.asc())
            .all()
        ]
        assert topics == ['First debate topic', 'Second debate topic']

    hub = client.get(f'/class-management/socrates/{session_id}')
    html = hub.get_data(as_text=True)
    assert 'First debate topic' in html
    assert 'Second debate topic' in html

    with app.app_context():
        _ensure_student_user()
    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    student = client.get('/class-management/student/socrates')
    student_html = student.get_data(as_text=True)
    assert 'First debate topic' in student_html
    assert 'Second debate topic' in student_html


def test_teacher_saves_numbered_instructions(app, client, teacher_user, class_session_w1, windows):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    page = client.get(f'/class-management/socrates/{session_id}')
    assert page.status_code == 200
    assert 'tinymce' in page.get_data(as_text=True)
    assert 'numlist' in page.get_data(as_text=True)

    rv = client.post(
        f'/class-management/socrates/{session_id}',
        data={
            'action': 'create',
            'topic': 'AI should be allowed in exams',
            'mode': 'individual',
            'prompt_limit': '8',
            'instructions': '<ol><li>Use case law</li><li>Define terms<script>alert(1)</script></li></ol>',
        },
        follow_redirects=True,
    )
    assert rv.status_code == 200
    with app.app_context():
        assignment = SocratesAssignment.query.filter_by(session_id=session_id).first()
        assert assignment is not None
        assert '<ol>' in assignment.instructions
        assert 'Use case law' in assignment.instructions
        assert '<script>' not in (assignment.instructions or '')
        assignment_id = assignment.id

    with app.app_context():
        _ensure_student_user()
    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    chat = client.get(f'/class-management/student/socrates/{assignment_id}')
    html = chat.get_data(as_text=True)
    assert '<ol>' in html
    assert 'Use case law' in html


def test_manage_404_for_other_window(app, client, teacher_user, class_session_w2, windows):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.get(f"/class-management/socrates/{class_session_w2['session_id']}")
    assert rv.status_code == 404


@patch('utils.ai.socrates.generate_socrates_reply')
def test_student_chat_respects_prompt_limit(mock_reply, app, client, teacher_user, class_session_w1, windows):
    mock_reply.return_value = 'But what is your authority for that claim?'
    session_id = class_session_w1['session_id']

    with app.app_context():
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'], prompt_limit=2)
        _ensure_student_user()

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])

    page = client.get(f'/class-management/student/socrates/{assignment_id}')
    assert page.status_code == 200

    for _ in range(2):
        rv = client.post(
            f'/class-management/student/socrates/{assignment_id}/send',
            json={'message': 'The death penalty violates the right to life.'},
        )
        assert rv.status_code == 200
        assert rv.get_json()['success'] is True

    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'One more argument.'},
    )
    assert rv.status_code == 400
    assert rv.get_json()['success'] is False
    assert mock_reply.call_count == 2

    with app.app_context():
        convo = SocratesConversation.query.filter_by(assignment_id=assignment_id, student_id='S001').first()
        assert convo.prompts_used == 2
        assert len(convo.messages) == 4  # 2 student + 2 socrates


@patch('utils.ai.socrates.generate_socrates_reply')
def test_prompt_refunded_when_ai_fails(mock_reply, app, client, teacher_user, class_session_w1, windows):
    mock_reply.side_effect = ValueError('এআই উত্তর দেয়নি। আবার চেষ্টা করুন।')
    session_id = class_session_w1['session_id']

    with app.app_context():
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'])
        _ensure_student_user()

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'Opening argument.'},
    )
    assert rv.status_code == 400

    with app.app_context():
        convo = SocratesConversation.query.filter_by(assignment_id=assignment_id, student_id='S001').first()
        assert convo.prompts_used == 0
        assert len(convo.messages) == 0


def test_student_not_enrolled_gets_403(app, client, teacher_user, class_session_w1, windows):
    session_id = class_session_w1['session_id']
    with app.app_context():
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'])
        _ensure_student_user(username='S999', name='Outsider')

    login_client(client, 'S999', role='student', window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'I want in.'},
    )
    assert rv.status_code == 403


def test_group_student_without_group_blocked(app, client, teacher_user, class_session_w1, windows):
    session_id = class_session_w1['session_id']
    with app.app_context():
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'], mode='group')
        _ensure_student_user()

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'Group argument.'},
    )
    assert rv.status_code == 403


@patch('utils.ai.socrates.evaluate_conversation')
@patch('utils.ai.socrates.generate_socrates_reply')
def test_submit_triggers_evaluation_and_teacher_marks(
    mock_reply, mock_eval, app, client, teacher_user, class_session_w1, windows,
):
    mock_reply.return_value = 'Define "justice" before invoking it.'
    mock_eval.return_value = _fake_evaluation()
    session_id = class_session_w1['session_id']

    with app.app_context():
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'])
        _ensure_student_user()

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'Retribution is not justice.'},
    )
    assert rv.status_code == 200

    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/submit',
        follow_redirects=True,
    )
    assert rv.status_code == 200
    mock_eval.assert_called_once()

    with app.app_context():
        convo = SocratesConversation.query.filter_by(assignment_id=assignment_id, student_id='S001').first()
        assert convo.status == 'evaluated'
        stored = json.loads(convo.ai_evaluation_json)
        assert stored['suggested_score'] == 7.0
        convo_id = convo.id

    # Sending after submission is blocked
    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'One more thing.'},
    )
    assert rv.status_code == 400

    # Teacher reviews and marks
    teacher_client = app.test_client()
    login_client(teacher_client, teacher_user['username'], window_id=windows['w1_id'])
    page = teacher_client.get(f'/class-management/socrates/conversation/{convo_id}')
    assert page.status_code == 200
    assert 'Retribution is not justice.' in page.get_data(as_text=True)

    rv = teacher_client.post(
        f'/class-management/socrates/conversation/{convo_id}/mark',
        data={'teacher_mark': '8.5', 'teacher_comment': 'Well argued.'},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    with app.app_context():
        convo = SocratesConversation.query.get(convo_id)
        assert convo.teacher_mark == 8.5
        assert convo.teacher_comment == 'Well argued.'

    csv_resp = teacher_client.get(
        f'/class-management/socrates/{session_id}/assignment/{assignment_id}/marks.csv'
    )
    assert csv_resp.status_code == 200
    csv_text = csv_resp.get_data(as_text=True)
    assert '8.5' in csv_text
    assert 'S001' in csv_text


@patch('utils.ai.socrates.evaluate_conversation')
@patch('utils.ai.socrates.generate_socrates_reply')
def test_teacher_can_reopen_submitted_debate(
    mock_reply, mock_eval, app, client, teacher_user, class_session_w1, windows,
):
    mock_reply.return_value = 'And then?'
    mock_eval.return_value = _fake_evaluation()
    session_id = class_session_w1['session_id']

    with app.app_context():
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'], prompt_limit=1)
        _ensure_student_user()

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    assert client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'First argument.'},
    ).status_code == 200
    assert client.post(
        f'/class-management/student/socrates/{assignment_id}/submit',
        follow_redirects=True,
    ).status_code == 200
    assert client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'After submit.'},
    ).status_code == 400

    with app.app_context():
        convo = SocratesConversation.query.filter_by(assignment_id=assignment_id, student_id='S001').first()
        convo_id = convo.id
        assert convo.status == 'evaluated'

    teacher_client = app.test_client()
    login_client(teacher_client, teacher_user['username'], window_id=windows['w1_id'])
    rv = teacher_client.post(
        f'/class-management/socrates/conversation/{convo_id}/reopen',
        data={'extra_prompts': '3'},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    with app.app_context():
        convo = SocratesConversation.query.get(convo_id)
        assert convo.status == 'in_progress'
        assert convo.submitted_at is None
        assert convo.extra_prompts == 3
        assert convo.remaining_prompts() == 3

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    chat = client.get(f'/class-management/student/socrates/{assignment_id}')
    assert 'name="message"' in chat.get_data(as_text=True)
    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'Continuing the debate.'},
    )
    assert rv.status_code == 200
    assert rv.get_json()['success'] is True


@patch('utils.ai.socrates.generate_socrates_reply')
def test_group_conversation_is_shared(mock_reply, app, client, teacher_user, class_session_w1, windows):
    mock_reply.return_value = 'Interesting. And your evidence?'
    session_id = class_session_w1['session_id']

    with app.app_context():
        from blueprints.class_management.models import ClassStudent
        from blueprints.student_management.models import Student as StudentMgmt

        db.session.add(StudentMgmt(student_id='S002', name='Student Two'))
        db.session.add(ClassStudent(
            student_id='S002', name='Student Two',
            session_id=session_id, teacher_id=teacher_user['teacher_id'],
        ))
        assignment_id = _seed_assignment(session_id, teacher_user['teacher_id'], mode='group', prompt_limit=3)
        group = SocratesGroup(assignment_id=assignment_id, name='Group A')
        db.session.add(group)
        db.session.flush()
        db.session.add(SocratesGroupMember(group_id=group.id, student_id='S001', student_name='Student One'))
        db.session.add(SocratesGroupMember(group_id=group.id, student_id='S002', student_name='Student Two'))
        db.session.commit()
        _ensure_student_user('S001', 'Student One')
        _ensure_student_user('S002', 'Student Two')

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'We argue for reform.'},
    )
    assert rv.status_code == 200

    second = app.test_client()
    login_client(second, 'S002', role='student', window_id=windows['w1_id'])
    rv = second.post(
        f'/class-management/student/socrates/{assignment_id}/send',
        json={'message': 'Adding to our case: recidivism data.'},
    )
    assert rv.status_code == 200
    assert rv.get_json()['prompts_used'] == 2

    with app.app_context():
        convos = SocratesConversation.query.filter_by(assignment_id=assignment_id).all()
        assert len(convos) == 1
        assert convos[0].prompts_used == 2
        senders = {m.sender_student_id for m in convos[0].messages if m.sender == SocratesMessage.SENDER_STUDENT}
        assert senders == {'S001', 'S002'}

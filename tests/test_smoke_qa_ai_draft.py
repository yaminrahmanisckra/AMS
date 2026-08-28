"""Smoke tests: course Q&A AI draft endpoint."""
from unittest.mock import patch

from blueprints.class_management.models import (
    AnswerGuideline,
    CourseQuestionMessage,
    CourseQuestionThread,
)
from extensions import db
from tests.conftest import login_client


def _seed_qa_thread(session_id, teacher_id):
    thread = CourseQuestionThread(
        session_id=session_id,
        student_id='S001',
        student_name='Student One',
        teacher_id=teacher_id,
        subject='Magistrate jurisdiction',
        status='open',
    )
    db.session.add(thread)
    db.session.flush()
    msg = CourseQuestionMessage(
        thread_id=thread.id,
        sender_role='student',
        body='Can a magistrate try an offence punishable with 7 years?',
    )
    db.session.add(msg)
    db.session.commit()
    return thread.id, msg.id


def test_ai_draft_requires_guideline_text(app, client, teacher_user, class_session_w1, windows):
    with app.app_context():
        thread_id, msg_id = _seed_qa_thread(
            class_session_w1['session_id'],
            teacher_user['teacher_id'],
        )

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/course-questions/{thread_id}/ai-draft',
        json={'message_id': msg_id},
    )
    assert rv.status_code == 400
    assert rv.get_json()['success'] is False


@patch('utils.ai.qa_reply.generate_text_with_meta')
@patch('utils.ai.client.get_active_provider_setting')
def test_ai_draft_success_for_selected_message(
    mock_provider,
    mock_ai,
    app,
    client,
    teacher_user,
    class_session_w1,
    windows,
):
    mock_provider.return_value = {
        'provider': 'gemini',
        'api_key': 'test-key',
        'model_name': 'gemini-2.0-flash',
        'api_base_url': None,
        'temperature': 0.3,
        'max_tokens': 900,
    }
    mock_ai.return_value = {'text': '## উত্তর\nম্যাজিস্ট্রেট আদালতের এখতিয়ার...'}

    with app.app_context():
        db.session.add(
            AnswerGuideline(
                title='Faculty Answer Guideline',
                file_name='guideline.pdf',
                file_path='/tmp/guideline.pdf',
                extracted_text='Use IRAC for problem questions. Cite Bangladesh Penal Code sections.',
                is_active=True,
            )
        )
        thread_id, msg_id = _seed_qa_thread(
            class_session_w1['session_id'],
            teacher_user['teacher_id'],
        )

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/course-questions/{thread_id}/ai-draft',
        json={'message_id': msg_id},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True
    assert 'ম্যাজিস্ট্রেট' in data['draft']
    mock_ai.assert_called_once()


@patch('utils.ai.qa_reply.generate_text_with_meta')
@patch('utils.ai.client.get_active_provider_setting')
def test_ai_draft_404_for_other_window_session(
    mock_provider,
    mock_ai,
    app,
    client,
    teacher_user,
    class_session_w2,
    windows,
):
    mock_provider.return_value = {
        'provider': 'gemini',
        'api_key': 'test-key',
        'model_name': 'gemini-2.0-flash',
        'api_base_url': None,
        'temperature': 0.3,
        'max_tokens': 900,
    }
    mock_ai.return_value = {'text': 'Should not run'}

    with app.app_context():
        db.session.add(
            AnswerGuideline(
                title='G',
                file_name='g.pdf',
                file_path='/tmp/g.pdf',
                extracted_text='Guideline text',
                is_active=True,
            )
        )
        thread_id, msg_id = _seed_qa_thread(
            class_session_w2['session_id'],
            teacher_user['teacher_id'],
        )

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.post(
        f'/class-management/course-questions/{thread_id}/ai-draft',
        json={'message_id': msg_id},
    )
    assert rv.status_code == 404
    mock_ai.assert_not_called()

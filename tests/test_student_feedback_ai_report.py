"""Smoke tests: student feedback AI analysis endpoints."""
import json
from unittest.mock import patch

from blueprints.class_management.models import StudentFeedbackLink, StudentFeedbackResponse
from extensions import db
from tests.conftest import login_client


def _seed_feedback(session_id, with_response=True):
    link = StudentFeedbackLink(
        session_id=session_id,
        access_code='FBTESTCODE',
        title='Jurisprudence Feedback',
    )
    db.session.add(link)
    db.session.flush()
    if with_response:
        payload = {
            'academic_info': {'course_title': 'Jurisprudence'},
            'section_a': {
                'course_structure': 'Agree',
                'course_goals': 'Agree',
                'course_content_guidance': 'Agree',
                'course_interest': 'Agree',
            },
            'section_b': {
                'course_plan_discussed': 'Agree',
                'guidelines_received': 'Neutral',
                'assessment_helpful': 'Agree',
                'feedback_timely': 'Disagree',
            },
            'section_c': {},
            'section_d': {
                'likes': 'Structured lectures',
                'challenges': 'Late feedback on scripts',
                'suggestions': 'Return marked work sooner',
            },
        }
        db.session.add(StudentFeedbackResponse(
            feedback_link_id=link.id,
            payload=json.dumps(payload),
        ))
    db.session.commit()
    return link.id


def _ai_payload():
    return {
        'methodology': 'The survey was an anonymous eight-item Likert instrument administered online.',
        'quantitative_narrative': 'Timely feedback was the weakest item relative to the other ratings.',
        'qualitative_findings': [
            {
                'theme': 'Assessment and feedback',
                'comment_count': 1,
                'summary': 'A single respondent noted delayed return of marked work.',
                'quotation': 'Late feedback on scripts',
            }
        ],
        'triangulated_key_findings': [
            {
                'text': 'Item B4 is consistent with comments about delayed feedback.',
                'qa_area': 'teaching-learning and assessment',
            }
        ],
        'strengths': ['Course structure was rated favourably.'],
        'areas_requiring_improvement': ['Turnaround time for continuous assessment feedback.'],
        'action_plan': [
            {
                'issue': 'Turnaround time for continuous assessment feedback.',
                'proposed_action': 'Publish a two-week marking timetable.',
                'responsibility': 'Course teacher',
                'timeline': 'Next term',
                'verification': 'B4 mean in the following offering',
            }
        ],
        'limitations': ['Single-term data; findings are indicative.'],
        'excluded_comments_count': 0,
        'excluded_comments_reason': '',
    }


def test_ai_report_requires_teacher(app, client, teacher_user, class_session_w1, windows):
    with app.app_context():
        _seed_feedback(class_session_w1['session_id'])
        session_id = class_session_w1['session_id']

    rv = client.get(f'/class-management/evaluation/{session_id}/student-feedback/ai-report')
    assert rv.status_code in (302, 401)


def test_ai_analyze_requires_responses(app, client, teacher_user, class_session_w1, windows):
    with app.app_context():
        _seed_feedback(class_session_w1['session_id'], with_response=False)
        session_id = class_session_w1['session_id']

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.post(f'/class-management/evaluation/{session_id}/student-feedback/ai-analyze')
    assert rv.status_code == 400
    assert rv.get_json()['success'] is False


@patch('utils.ai.feedback_report.generate_feedback_report')
def test_ai_analyze_stores_report(
    mock_generate,
    app,
    client,
    teacher_user,
    class_session_w1,
    windows,
):
    def _fake_generate(dataset):
        dataset = dict(dataset)
        dataset['narrative'] = _ai_payload()
        return dataset

    mock_generate.side_effect = _fake_generate

    with app.app_context():
        _seed_feedback(class_session_w1['session_id'])
        session_id = class_session_w1['session_id']

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.post(f'/class-management/evaluation/{session_id}/student-feedback/ai-analyze')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True
    mock_generate.assert_called_once()

    page = client.get(f'/class-management/evaluation/{session_id}/student-feedback/ai-report')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'Course-wise Student Feedback Report' in html
    assert 'Turnaround time for continuous assessment feedback.' in html

    docx = client.get(f'/class-management/evaluation/{session_id}/student-feedback/ai-report/docx')
    assert docx.status_code == 200
    assert docx.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

    page_html = page.get_data(as_text=True)
    assert 'student-feedback/ai-report/pdf' in page_html


@patch('utils.pdf_fonts.resolve_dejavu_pdf_fonts')
@patch('utils.pdf_fonts.resolve_formal_pdf_fonts')
@patch('blueprints.class_management.routes._get_weasyprint_html')
def test_ai_report_pdf_download(
    mock_html,
    mock_fonts,
    mock_dejavu,
    app,
    client,
    teacher_user,
    class_session_w1,
    windows,
):
    from pathlib import Path

    class FakeHTML:
        def __init__(self, string, base_url=None):
            assert 'Course-wise Student Feedback Report' in string

        def write_pdf(self, buffer):
            buffer.write(b'%PDF-1.4 test')

    mock_html.return_value = FakeHTML
    mock_fonts.return_value = {
        'regular': 'file:///tmp/regular.ttf',
        'bold': 'file:///tmp/bold.ttf',
        'fonts_dir': Path('/tmp'),
    }
    mock_dejavu.return_value = (None, None, None)

    with app.app_context():
        link_id = _seed_feedback(class_session_w1['session_id'])
        link = StudentFeedbackLink.query.get(link_id)
        link.ai_report_json = json.dumps({
            'generated_at': '2026-09-15 09:00 UTC',
            'discipline': 'Law Discipline, Khulna University',
            'indicative_only': False,
            'profile': [{'field': 'Course code and title', 'value': 'LAW 1101 — Jurisprudence'}],
            'quantitative': {'likert_items': [], 'overall_mean': 4.1},
            'comments': [{'likes': 'Clear lectures'}],
            'narrative': _ai_payload(),
        })
        db.session.commit()
        session_id = class_session_w1['session_id']

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.get(f'/class-management/evaluation/{session_id}/student-feedback/ai-report/pdf')
    assert rv.status_code == 200
    assert rv.mimetype == 'application/pdf'
    assert rv.data.startswith(b'%PDF')


@patch('utils.ai.feedback_report.generate_feedback_report')
def test_ai_analyze_404_for_other_window(
    mock_generate,
    app,
    client,
    teacher_user,
    class_session_w2,
    windows,
):
    mock_generate.side_effect = AssertionError('AI should not run')

    with app.app_context():
        _seed_feedback(class_session_w2['session_id'])
        session_id = class_session_w2['session_id']

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.post(f'/class-management/evaluation/{session_id}/student-feedback/ai-analyze')
    assert rv.status_code == 404
    mock_generate.assert_not_called()

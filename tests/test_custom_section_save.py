"""Custom section rich-text body persists in assessment_strategy."""
import json

from blueprints.class_management.models import CourseOutline
from extensions import db
from tests.conftest import login_client


def test_save_custom_section_body(app, client, teacher_user, class_session_w1, windows):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    session_id = class_session_w1['session_id']
    body_html = '<p>Plagiarism policy text</p><table border="1"><tbody><tr><td>A</td><td>B</td></tr></tbody></table>'

    rv = client.post(
        f'/class-management/course_file/{session_id}/save',
        json={
            'assessment_strategy': {
                'custom_section_enabled': True,
                'custom_section_header': 'Plagiarism Policy',
                'custom_section_body': body_html,
                'attendance_percent': '10',
                'ca_percent': '40',
                'final_exam_percent': '60',
            },
        },
    )
    assert rv.status_code == 200
    assert rv.get_json()['success'] is True

    with app.app_context():
        outline = CourseOutline.query.filter_by(session_id=session_id).first()
        assert outline is not None
        strategy = json.loads(outline.assessment_strategy or '{}')
        assert strategy.get('custom_section_header') == 'Plagiarism Policy'
        assert 'Plagiarism policy text' in strategy.get('custom_section_body', '')
        assert '<table' in strategy.get('custom_section_body', '')

"""INJ-01: notice body HTML is sanitized on save and render."""
from datetime import date

from blueprints.noticeboard.models import Notice
from blueprints.noticeboard.routes import _sanitize_notice_html
from extensions import db
from tests.conftest import login_client
from utils.outline_richtext import html_is_empty


XSS_PAYLOAD = '<p>Hello</p><script>alert(1)</script><img src=x onerror="alert(1)">'


def test_sanitize_strips_script_and_event_handlers():
    cleaned = _sanitize_notice_html(XSS_PAYLOAD)
    assert '<script>' not in cleaned.lower()
    assert 'alert(1)' not in cleaned
    assert 'onerror' not in cleaned.lower()
    assert 'Hello' in cleaned
    assert not html_is_empty(cleaned)


def test_sanitize_blocks_javascript_href():
    cleaned = _sanitize_notice_html('<a href="javascript:alert(1)">Click</a>')
    assert 'javascript:' not in cleaned.lower()
    assert 'Click' in cleaned


def test_script_only_body_is_empty():
    assert html_is_empty(_sanitize_notice_html('<script>alert(1)</script>'))


def test_create_persists_sanitized_html(client, app, teacher_user, class_session_w1, windows):
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.post(
        '/noticeboard/create',
        data={
            'title': 'Exam notice',
            'body_html': XSS_PAYLOAD,
            'notice_date': '2026-09-08',
            'audience_sessions': str(class_session_w1['session_id']),
        },
        follow_redirects=False,
    )
    assert rv.status_code in (302, 303)

    with app.app_context():
        notice = Notice.query.order_by(Notice.id.desc()).first()
        assert notice is not None
        assert '<script>' not in (notice.body_html or '').lower()
        assert 'alert(1)' not in (notice.body_html or '')
        assert 'Hello' in notice.body_html


def test_detail_strips_legacy_stored_xss(client, app, teacher_user, windows):
    with app.app_context():
        notice = Notice(
            title='Legacy XSS',
            body_html=XSS_PAYLOAD,
            author_user_id=teacher_user['user_id'],
            notice_date=date(2026, 9, 8),
            window_id=windows['w1_id'],
        )
        db.session.add(notice)
        db.session.commit()
        notice_id = notice.id

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    rv = client.get(f'/noticeboard/{notice_id}')
    assert rv.status_code == 200
    html = rv.data.decode('utf-8', errors='replace')
    assert '<script>alert(1)</script>' not in html.lower()
    assert 'onerror' not in html.lower()
    assert 'alert(1)' not in html
    assert 'Hello' in html

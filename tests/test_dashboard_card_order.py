"""Teachers can save a personal order for main-dashboard cards."""
import json

from tests.conftest import login_client


def test_teacher_dashboard_order_persists(client, teacher_user, app):
    login_client(client, teacher_user['username'], role='teacher', window_id=teacher_user and 1)

    page = client.get('/')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'data-arrange="1"' in html
    assert 'dashboard-card-grip' not in html
    class_at = html.find('data-card-key="class_management"')
    routine_at = html.find('data-card-key="routine_management"')
    assert class_at != -1 and routine_at != -1
    assert class_at < routine_at

    saved = client.post(
        '/dashboard/card-order',
        data=json.dumps({'order': ['routine_management', 'class_management', 'remuneration']}),
        content_type='application/json',
    )
    assert saved.status_code == 200
    assert saved.get_json()['ok'] is True

    again = client.get('/')
    html = again.get_data(as_text=True)
    assert html.find('data-card-key="routine_management"') < html.find('data-card-key="class_management"')

    from extensions import db
    from user_models import User

    with app.app_context():
        user = db.session.get(User, teacher_user['user_id'])
        assert json.loads(user.dashboard_card_order)[0] == 'routine_management'

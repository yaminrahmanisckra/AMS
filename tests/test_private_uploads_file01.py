"""FILE-01/02: private upload root dual-read + authenticated media routes."""
import os

from flask import Flask

from tests.conftest import TEST_PASSWORD, login_client
from utils.private_uploads import private_token_filename, store_relative
from utils.safe_files import confined_existing_file
from extensions import db
from user_models import User


def _app_with_private(tmp_path):
    root = tmp_path / 'app'
    static_uploads = root / 'static' / 'uploads'
    private = tmp_path / 'private'
    static_uploads.mkdir(parents=True)
    private.mkdir(parents=True)
    (private / 'user_photos').mkdir()
    app = Flask('private_uploads_test')
    app.root_path = str(root)
    app.static_folder = str(root / 'static')
    app.config['PRIVATE_UPLOAD_DIR'] = str(private)
    return app, static_uploads, private


def test_private_token_filename_is_opaque():
    name = private_token_filename('jpg')
    assert name.endswith('.jpg')
    assert 'user_' not in name
    stem = name.rsplit('.', 1)[0]
    assert len(stem) >= 16


def test_confined_reads_private_relative_path(tmp_path):
    app, _static, private = _app_with_private(tmp_path)
    photo = private / 'user_photos' / 'tok123.jpg'
    photo.write_bytes(b'jpg')
    with app.app_context():
        found = confined_existing_file('user_photos/tok123.jpg')
        assert found == os.path.realpath(photo)


def test_confined_dual_reads_legacy_static_path_from_private_copy(tmp_path):
    """After rsync, DB may still say /static/uploads/... while bytes live in private root."""
    app, _static, private = _app_with_private(tmp_path)
    photo = private / 'user_photos' / 'legacy.jpg'
    photo.write_bytes(b'jpg')
    with app.app_context():
        found = confined_existing_file('/static/uploads/user_photos/legacy.jpg')
        assert found == os.path.realpath(photo)


def test_confined_still_reads_legacy_static_file(tmp_path):
    app, static_uploads, _private = _app_with_private(tmp_path)
    folder = static_uploads / 'user_photos'
    folder.mkdir(parents=True)
    photo = folder / 'old.jpg'
    photo.write_bytes(b'jpg')
    with app.app_context():
        found = confined_existing_file('/static/uploads/user_photos/old.jpg')
        assert found == os.path.realpath(photo)


def test_media_photo_requires_login(client, teacher_user):
    with client.application.app_context():
        user = User.query.get(teacher_user['user_id'])
        user.photo = store_relative('user_photos', 'x.jpg')
        db.session.commit()
    rv = client.get(f"/media/users/{teacher_user['user_id']}/photo")
    assert rv.status_code in (302, 401, 403)


def test_media_photo_owner_ok_other_forbidden(client, teacher_user, app, tmp_path, monkeypatch, windows):
    private = tmp_path / 'media_private'
    (private / 'user_photos').mkdir(parents=True)
    photo_name = 'own.jpg'
    (private / 'user_photos' / photo_name).write_bytes(b'\xff\xd8\xff')
    monkeypatch.setenv('PRIVATE_UPLOAD_DIR', str(private))
    app.config['PRIVATE_UPLOAD_DIR'] = str(private)

    with app.app_context():
        owner = User.query.get(teacher_user['user_id'])
        owner.photo = store_relative('user_photos', photo_name)
        other = User(
            username='other1',
            email='other1@test.example',
            full_name='Other User',
            role='teacher',
        )
        other.set_password(TEST_PASSWORD)
        db.session.add(other)
        db.session.commit()
        other_id = other.id
        owner_id = owner.id

    login_client(client, teacher_user['username'], role='teacher', window_id=windows['w1_id'])
    ok = client.get(f'/media/users/{owner_id}/photo')
    assert ok.status_code == 200

    denied = client.get(f'/media/users/{other_id}/photo')
    assert denied.status_code in (403, 404)


def test_media_signature_admin_can_view(client, teacher_user, app, tmp_path, monkeypatch, windows):
    private = tmp_path / 'sig_private'
    (private / 'user_signatures').mkdir(parents=True)
    sig_name = 'sig.png'
    (private / 'user_signatures' / sig_name).write_bytes(b'\x89PNG\r\n\x1a\n')
    monkeypatch.setenv('PRIVATE_UPLOAD_DIR', str(private))
    app.config['PRIVATE_UPLOAD_DIR'] = str(private)

    with app.app_context():
        teacher = User.query.get(teacher_user['user_id'])
        teacher.signature_path = store_relative('user_signatures', sig_name)
        admin = User(
            username='adminmedia',
            email='adminmedia@test.example',
            full_name='Admin Media',
            role='admin',
        )
        admin.set_password(TEST_PASSWORD)
        db.session.add(admin)
        db.session.commit()
        teacher_id = teacher.id

    login_client(client, 'adminmedia', role='admin', window_id=None)
    rv = client.get(f'/media/users/{teacher_id}/signature')
    assert rv.status_code == 200

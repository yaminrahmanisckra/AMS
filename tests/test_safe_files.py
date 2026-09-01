"""Upload path confinement: refuse files outside static/uploads and uploads/."""
import os

from flask import Flask

from utils.safe_files import confined_existing_file, send_confined_file


def _app_with_uploads(tmp_path):
    root = tmp_path / 'app'
    uploads = root / 'static' / 'uploads'
    uploads.mkdir(parents=True)
    app = Flask('safe_files_test')
    app.root_path = str(root)
    app.static_folder = str(root / 'static')
    return app, uploads


def test_confined_file_allows_upload_dir(tmp_path):
    app, uploads = _app_with_uploads(tmp_path)
    good = uploads / 'photo.jpg'
    good.write_bytes(b'jpg')
    with app.app_context():
        found = confined_existing_file(str(good))
        assert found == os.path.realpath(good)
        found_rel = confined_existing_file('static/uploads/photo.jpg')
        assert found_rel == os.path.realpath(good)


def test_confined_file_rejects_outside_upload_dir(tmp_path):
    app, _uploads = _app_with_uploads(tmp_path)
    evil = tmp_path / 'secret.txt'
    evil.write_text('nope')
    with app.app_context():
        assert confined_existing_file(str(evil)) is None
        assert confined_existing_file('/etc/passwd') is None
        assert confined_existing_file('../secret.txt') is None


def test_send_confined_file_404_outside(tmp_path):
    app, _uploads = _app_with_uploads(tmp_path)
    evil = tmp_path / 'secret.txt'
    evil.write_text('nope')

    @app.route('/dl')
    def dl():
        return send_confined_file(str(evil))

    client = app.test_client()
    assert client.get('/dl').status_code == 404

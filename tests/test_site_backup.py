"""Site backup archives, path safety, and restore scope."""
import json
import os
import sqlite3
import zipfile

from utils.site_backup import (
    apply_restore,
    build_archive,
    dump_database,
    restore_database,
)


def _sqlite_url(path):
    return 'sqlite:///' + os.path.abspath(path)


def test_sqlite_dump_roundtrip(tmp_path):
    db_path = tmp_path / 'app.db'
    conn = sqlite3.connect(db_path)
    conn.execute('create table note (id integer primary key, body text)')
    conn.execute('insert into note (id, body) values (1, ?)', ('hello\nworld',))
    conn.commit()
    conn.close()

    dump_path = tmp_path / 'dump.sql'
    assert dump_database(_sqlite_url(db_path), str(dump_path)) == 'sqlite'

    conn = sqlite3.connect(db_path)
    conn.execute("update note set body = 'changed'")
    conn.commit()
    conn.close()

    restore_database(_sqlite_url(db_path), str(dump_path))
    conn = sqlite3.connect(db_path)
    body = conn.execute('select body from note where id = 1').fetchone()[0]
    conn.close()
    assert body == 'hello\nworld'


def test_archive_skips_env_and_restores_only_selected_files(tmp_path):
    project = tmp_path / 'project'
    private = tmp_path / 'private'
    instance = tmp_path / 'instance'
    (project / 'uploads').mkdir(parents=True)
    (private / 'user_photos').mkdir(parents=True)
    instance.mkdir()
    (project / 'app.py').write_text('print(1)\n', encoding='utf-8')
    (project / '.env').write_text('SECRET=1\n', encoding='utf-8')
    (private / 'user_photos' / 'a.jpg').write_bytes(b'photo')
    (instance / 'academic_rules_law.yaml').write_text('grade: A\n', encoding='utf-8')

    db_path = tmp_path / 'app.db'
    sqlite3.connect(db_path).close()
    zip_path = tmp_path / 'backup.zip'
    manifest = build_archive(str(zip_path), ['database', 'photos', 'settings', 'code'], {
        'database_url': _sqlite_url(db_path),
        'private_root': str(private),
        'project_root': str(project),
        'instance_root': str(instance),
    })
    assert 'code' in manifest['parts']
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert 'code/app.py' in names
    assert 'code/.env' not in names
    assert all(not name.endswith('.env') for name in names)
    assert 'files/user_photos/a.jpg' in names
    assert 'settings/academic_rules_law.yaml' in names

    (private / 'user_photos' / 'a.jpg').write_bytes(b'changed')
    (private / 'user_photos' / 'extra.jpg').write_bytes(b'gone')
    apply_restore(str(zip_path), ['photos', 'code'], {
        'database_url': _sqlite_url(db_path),
        'private_root': str(private),
        'project_root': str(project),
        'instance_root': str(instance),
    })
    assert (private / 'user_photos' / 'a.jpg').read_bytes() == b'photo'
    assert not (private / 'user_photos' / 'extra.jpg').exists()
    assert (project / 'app.py').read_text(encoding='utf-8') == 'print(1)\n'


def test_backup_page_requires_an_admin(client, app):
    response = client.get('/admin/backup/')
    assert response.status_code in (302, 401)
    assert 'login' in (response.headers.get('Location') or '')

    with app.test_request_context('/admin/backup/upload', method='POST'):
        from flask import request
        assert request.max_content_length == 1024 * 1024 * 1024
    with app.test_request_context('/admin/users'):
        from flask import request
        assert request.max_content_length == 16 * 1024 * 1024


def test_restore_rejects_path_escape(tmp_path):
    private = tmp_path / 'private'
    (private / 'user_photos').mkdir(parents=True)
    outside = tmp_path / 'secret.txt'
    zip_path = tmp_path / 'evil.zip'
    manifest = {
        'format': 1,
        'kind': 'backup',
        'created_at': '2026-11-22T00:00:00Z',
        'parts': ['photos'],
        'counts': {},
        'database_engine': None,
    }
    with zipfile.ZipFile(zip_path, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        archive.writestr('files/user_photos/ok.txt', 'ok')
        archive.writestr('files/user_photos/../../secret.txt', 'nope')
        archive.writestr('code/.env', 'SECRET=1')
    apply_restore(str(zip_path), ['photos', 'code'], {
        'database_url': 'sqlite:///' + str(tmp_path / 'unused.db'),
        'private_root': str(private),
        'project_root': str(tmp_path / 'project'),
        'instance_root': str(tmp_path / 'instance'),
    })
    assert (private / 'user_photos' / 'ok.txt').read_text(encoding='utf-8') == 'ok'
    assert not outside.exists()
    assert not (tmp_path / 'secret.txt').exists()

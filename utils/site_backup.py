"""Admin site backup and restore.

Archives live in ~/ams_backups (outside the app and outside public_html).
A zip may contain any of: database, photos, signatures, admission files,
course uploads, instance settings, and application code.

Code is for download only. Restore never writes the application source or
environment files.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import uuid
import zipfile
from datetime import datetime, date, time
from decimal import Decimal

from sqlalchemy.engine.url import make_url

FORMAT = 1
RESTORE_PHRASE = 'RESTORE'
MAX_UNCOMPRESSED = 8 * 1024 * 1024 * 1024
MAX_MEMBERS = 200_000
KEEP_BACKUPS = 8
KEEP_SAFETY = 5

PARTS = (
    ('database', 'Database', 'Tables and rows. Does not include the database password.'),
    ('photos', 'Photos', 'Profile and applicant photos.'),
    ('signatures', 'Signatures', 'User and applicant signatures.'),
    ('admission', 'Admission files', 'Slips, certificates, and other admission uploads.'),
    ('course_files', 'Course files', 'Course files, question bank, and Q&A uploads.'),
    ('settings', 'Saved settings', 'Academic rules and remuneration rates saved on this server.'),
    ('code', 'Application code', 'Download only. Restore does not replace the running program.'),
)

PART_KEYS = {key for key, _label, _help in PARTS}
RESTORABLE = PART_KEYS - {'code'}

_CODE_SKIP_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', 'node_modules', '.cursor',
    'tmp', '.pytest_cache', 'htmlcov', 'dist', 'build', '.mypy_cache',
    'ams_backups',
}
_CODE_SKIP_FILES = {'.ds_store'}
_LOCK = threading.Lock()


def backup_root() -> str:
    root = os.path.join(os.path.expanduser('~'), 'ams_backups')
    os.makedirs(root, mode=0o700, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    return root


def part_label(key: str) -> str:
    for part_key, label, _help in PARTS:
        if part_key == key:
            return label
    return key


def _progress(callback, message):
    if callback:
        callback(message)


def _dir_size(path: str) -> int:
    total = 0
    if not path or not os.path.isdir(path):
        return 0
    for current, dirs, files in os.walk(path):
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(current, name))]
        for name in files:
            full = os.path.join(current, name)
            if os.path.islink(full):
                continue
            try:
                total += os.path.getsize(full)
            except OSError:
                continue
    return total


def describe_parts(private_root: str, project_root: str, instance_root: str) -> list[dict]:
    """Sizes shown next to the checkboxes. Missing folders count as zero."""
    static_uploads = os.path.join(project_root, 'static', 'uploads')
    mapping = {
        'photos': [
            os.path.join(private_root, 'user_photos'),
            os.path.join(static_uploads, 'user_photos'),
        ],
        'signatures': [
            os.path.join(private_root, 'user_signatures'),
            os.path.join(static_uploads, 'user_signatures'),
        ],
        'admission': [
            os.path.join(private_root, 'admission_exam'),
            os.path.join(static_uploads, 'admission_exam'),
        ],
        'course_files': [os.path.join(project_root, 'uploads')],
        'settings': [instance_root],
    }
    rows = []
    for key, label, help_text in PARTS:
        size = 0
        if key in mapping:
            size = sum(_dir_size(path) for path in mapping[key])
            if key == 'settings':
                size = sum(
                    os.path.getsize(path)
                    for path in _settings_files(instance_root)
                    if os.path.isfile(path)
                )
        rows.append({
            'key': key,
            'label': label,
            'help': help_text,
            'size': size,
            'restorable': key in RESTORABLE,
        })
    return rows


def format_size(num: int) -> str:
    value = float(num or 0)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            if unit == 'B':
                return f'{int(value)} {unit}'
            return f'{value:.1f} {unit}'
        value /= 1024
    return f'{value:.1f} GB'


def _settings_files(instance_root: str) -> list[str]:
    if not instance_root or not os.path.isdir(instance_root):
        return []
    found = []
    for name in sorted(os.listdir(instance_root)):
        lower = name.lower()
        if not (lower.startswith('academic_rules') or lower.startswith('remuneration_rates')):
            continue
        if not (lower.endswith('.yaml') or lower.endswith('.yml')):
            continue
        found.append(os.path.join(instance_root, name))
    return found


def _sql_literal(value) -> str:
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, Decimal)):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            return 'NULL'
        return repr(value)
    if isinstance(value, datetime):
        return "'" + value.strftime('%Y-%m-%d %H:%M:%S') + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(value, time):
        return "'" + value.strftime('%H:%M:%S') + "'"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "X'" + bytes(value).hex() + "'"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value)
    text = (
        text.replace('\\', '\\\\')
        .replace("'", "\\'")
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('\x00', '\\0')
    )
    return "'" + text + "'"


def _quote_ident(name: str) -> str:
    return '`' + str(name).replace('`', '``') + '`'


def dump_database(database_url: str, dest_path: str, progress=None) -> str:
    """Write a restorable SQL script. Returns 'sqlite' or 'mysql'."""
    url = make_url(database_url)
    engine_name = 'sqlite' if url.get_backend_name() == 'sqlite' else 'mysql'
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    if engine_name == 'sqlite':
        _progress(progress, 'Copying SQLite database')
        _dump_sqlite(url.database, dest_path)
    else:
        _progress(progress, 'Copying MySQL database')
        _dump_mysql(database_url, dest_path)
    return engine_name


def _dump_sqlite(db_path: str, dest_path: str) -> None:
    if not db_path or not os.path.isfile(db_path):
        raise RuntimeError('SQLite database file was not found.')
    conn = sqlite3.connect(db_path, timeout=60)
    try:
        with open(dest_path, 'w', encoding='utf-8') as handle:
            handle.write('-- AMS sqlite dump\n')
            for line in conn.iterdump():
                handle.write(line)
                handle.write('\n')
    finally:
        conn.close()


def _dump_mysql(database_url: str, dest_path: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text('START TRANSACTION WITH CONSISTENT SNAPSHOT'))
            except Exception:
                pass
            rows = conn.execute(text('SHOW FULL TABLES')).fetchall()
            tables = [row[0] for row in rows if len(row) < 2 or str(row[1]).upper() == 'BASE TABLE']
            with open(dest_path, 'w', encoding='utf-8') as handle:
                handle.write('-- AMS mysql dump\n')
                handle.write('SET NAMES utf8mb4;\n')
                handle.write('SET FOREIGN_KEY_CHECKS=0;\n')
                for table in tables:
                    ddl_row = conn.execute(text(f'SHOW CREATE TABLE {_quote_ident(table)}')).fetchone()
                    ddl = str(ddl_row[1]).replace('\r\n', '\n').replace('\n', ' ')
                    handle.write(f'DROP TABLE IF EXISTS {_quote_ident(table)};\n')
                    if not ddl.endswith(';'):
                        ddl += ';'
                    handle.write(ddl + '\n')
                    _dump_mysql_rows(conn, table, handle)
                handle.write('SET FOREIGN_KEY_CHECKS=1;\n')
            try:
                conn.commit()
            except Exception:
                pass
    finally:
        engine.dispose()


def _dump_mysql_rows(conn, table: str, handle) -> None:
    from sqlalchemy import text

    result = conn.execute(text(f'SELECT * FROM {_quote_ident(table)}'))
    columns = list(result.keys())
    if not columns:
        return
    col_sql = ', '.join(_quote_ident(name) for name in columns)
    batch = []
    batch_chars = 0

    def flush():
        nonlocal batch, batch_chars
        if not batch:
            return
        handle.write(
            f'INSERT INTO {_quote_ident(table)} ({col_sql}) VALUES ' + ','.join(batch) + ';\n'
        )
        batch = []
        batch_chars = 0

    for row in result:
        values = ','.join(_sql_literal(value) for value in row)
        piece = '(' + values + ')'
        if batch and batch_chars + len(piece) > 800_000:
            flush()
        batch.append(piece)
        batch_chars += len(piece)
    flush()


def restore_database(database_url: str, dump_path: str, progress=None) -> str:
    url = make_url(database_url)
    engine_name = 'sqlite' if url.get_backend_name() == 'sqlite' else 'mysql'
    if engine_name == 'sqlite':
        _progress(progress, 'Restoring SQLite database')
        _restore_sqlite(url.database, dump_path)
    else:
        _progress(progress, 'Restoring MySQL database')
        _restore_mysql(database_url, dump_path)
    return engine_name


def _restore_sqlite(db_path: str, dump_path: str) -> None:
    conn = sqlite3.connect(db_path, timeout=120)
    try:
        conn.execute('PRAGMA foreign_keys=OFF')
        rows = conn.execute(
            "SELECT type, name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' AND type IN ('trigger', 'view', 'index', 'table')"
        ).fetchall()
        order = {'trigger': 0, 'view': 1, 'index': 2, 'table': 3}
        rows = sorted(rows, key=lambda row: order.get(row[0], 9))
        for kind, name in rows:
            quoted = '"' + str(name).replace('"', '""') + '"'
            if kind == 'trigger':
                conn.execute(f'DROP TRIGGER IF EXISTS {quoted}')
            elif kind == 'view':
                conn.execute(f'DROP VIEW IF EXISTS {quoted}')
            elif kind == 'index':
                conn.execute(f'DROP INDEX IF EXISTS {quoted}')
            else:
                conn.execute(f'DROP TABLE IF EXISTS {quoted}')
        conn.commit()
        with open(dump_path, 'r', encoding='utf-8') as handle:
            script = handle.read()
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()


def _restore_mysql(database_url: str, dump_path: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, pool_pre_ping=True)
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute('SET FOREIGN_KEY_CHECKS=0')
        with open(dump_path, 'r', encoding='utf-8') as handle:
            for line in handle:
                statement = line.strip()
                if not statement or statement.startswith('--'):
                    continue
                cursor.execute(statement)
        cursor.execute('SET FOREIGN_KEY_CHECKS=1')
        raw.commit()
    except Exception:
        try:
            raw.rollback()
        except Exception:
            pass
        raise
    finally:
        raw.close()
        engine.dispose()


def _add_tree(archive: zipfile.ZipFile, source: str, arc_prefix: str) -> int:
    if not source or not os.path.isdir(source):
        return 0
    count = 0
    for current, dirs, files in os.walk(source):
        dirs[:] = [
            name for name in dirs
            if not os.path.islink(os.path.join(current, name)) and name not in _CODE_SKIP_DIRS
        ]
        for name in files:
            full = os.path.join(current, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, source).replace('\\', '/')
            archive.write(full, f'{arc_prefix}/{rel}')
            count += 1
    return count


def _add_code(archive: zipfile.ZipFile, project_root: str) -> int:
    count = 0
    project_root = os.path.abspath(project_root)
    for current, dirs, files in os.walk(project_root):
        dirs[:] = [
            name for name in dirs
            if name not in _CODE_SKIP_DIRS
            and not os.path.islink(os.path.join(current, name))
            and name != 'uploads'
        ]
        rel_dir = os.path.relpath(current, project_root).replace('\\', '/')
        if rel_dir == '.':
            rel_dir = ''
        if rel_dir == 'instance' or rel_dir.startswith('instance/') or rel_dir == 'static/uploads' or rel_dir.startswith('static/uploads/'):
            dirs[:] = []
            continue
        for name in files:
            lower = name.lower()
            if lower in _CODE_SKIP_FILES or lower == '.env' or lower.startswith('.env.'):
                continue
            if lower.endswith(('.pem', '.pyc', '.pyo')):
                continue
            full = os.path.join(current, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, project_root).replace('\\', '/')
            archive.write(full, f'code/{rel}')
            count += 1
    return count


def build_archive(zip_path: str, parts: list[str], locations: dict, progress=None, kind: str = 'backup') -> dict:
    selected = [part for part in parts if part in PART_KEYS]
    if not selected:
        raise RuntimeError('Choose at least one item to back up.')
    os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)
    tmp_zip = zip_path + '.partial'
    counts = {}
    engine_name = None
    dump_tmp = None
    try:
        with zipfile.ZipFile(tmp_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            if 'database' in selected:
                dump_tmp = tmp_zip + '.sql'
                engine_name = dump_database(locations['database_url'], dump_tmp, progress)
                archive.write(dump_tmp, 'database/dump.sql')
                counts['database'] = 1
            private = locations.get('private_root') or ''
            project = locations.get('project_root') or ''
            static_uploads = os.path.join(project, 'static', 'uploads')
            file_parts = {
                'photos': [
                    (os.path.join(private, 'user_photos'), 'files/user_photos'),
                    (os.path.join(static_uploads, 'user_photos'), 'files/legacy_static/user_photos'),
                ],
                'signatures': [
                    (os.path.join(private, 'user_signatures'), 'files/user_signatures'),
                    (os.path.join(static_uploads, 'user_signatures'), 'files/legacy_static/user_signatures'),
                ],
                'admission': [
                    (os.path.join(private, 'admission_exam'), 'files/admission_exam'),
                    (os.path.join(static_uploads, 'admission_exam'), 'files/legacy_static/admission_exam'),
                ],
                'course_files': [
                    (os.path.join(project, 'uploads'), 'files/course_uploads'),
                ],
            }
            for part, trees in file_parts.items():
                if part not in selected:
                    continue
                _progress(progress, f'Adding {part_label(part).lower()}')
                counts[part] = sum(_add_tree(archive, src, arc) for src, arc in trees)
            if 'settings' in selected:
                _progress(progress, 'Adding saved settings')
                added = 0
                for path in _settings_files(locations.get('instance_root') or ''):
                    archive.write(path, 'settings/' + os.path.basename(path))
                    added += 1
                counts['settings'] = added
            if 'code' in selected:
                _progress(progress, 'Adding application code')
                counts['code'] = _add_code(archive, project)
            manifest = {
                'format': FORMAT,
                'kind': kind,
                'created_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'parts': selected,
                'counts': counts,
                'database_engine': engine_name,
                'excludes': ['.env', 'passwords', 'virtualenv', 'backup folder'],
            }
            archive.writestr('manifest.json', json.dumps(manifest, indent=2))
        os.replace(tmp_zip, zip_path)
        return manifest
    except Exception:
        for path in (tmp_zip, dump_tmp):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        raise
    finally:
        if dump_tmp and os.path.exists(dump_tmp):
            try:
                os.remove(dump_tmp)
            except OSError:
                pass


def read_manifest(zip_path: str) -> dict:
    with zipfile.ZipFile(zip_path) as archive:
        try:
            raw = archive.read('manifest.json')
        except KeyError as exc:
            raise RuntimeError('This zip is not an AMS backup.') from exc
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        raise RuntimeError('This backup was made by a different version.')
    parts = [part for part in data.get('parts') or [] if part in PART_KEYS]
    data['parts'] = parts
    return data


def _member_allowed(name: str, prefixes: tuple[str, ...]) -> bool:
    clean = name.replace('\\', '/').lstrip('/')
    if not clean or clean.startswith('/') or any(piece == '..' for piece in clean.split('/')):
        return False
    return any(clean == prefix or clean.startswith(prefix + '/') for prefix in prefixes)


def _prefixes_for(parts: list[str]) -> tuple[str, ...]:
    prefixes = []
    if 'database' in parts:
        prefixes.append('database/dump.sql')
    mapping = {
        'photos': ('files/user_photos', 'files/legacy_static/user_photos'),
        'signatures': ('files/user_signatures', 'files/legacy_static/user_signatures'),
        'admission': ('files/admission_exam', 'files/legacy_static/admission_exam'),
        'course_files': ('files/course_uploads',),
        'settings': ('settings',),
    }
    for part in parts:
        prefixes.extend(mapping.get(part, ()))
    return tuple(prefixes)


def _safe_extract(archive: zipfile.ZipFile, dest: str, prefixes: tuple[str, ...]) -> None:
    os.makedirs(dest, exist_ok=True)
    total = 0
    members = archive.infolist()
    if len(members) > MAX_MEMBERS:
        raise RuntimeError('Backup contains too many files.')
    for info in members:
        if info.is_dir():
            continue
        if not _member_allowed(info.filename, prefixes):
            continue
        total += info.file_size
        if total > MAX_UNCOMPRESSED:
            raise RuntimeError('Backup is larger than the restore limit.')
        target = os.path.abspath(os.path.join(dest, info.filename.replace('\\', '/')))
        if not target.startswith(os.path.abspath(dest) + os.sep):
            raise RuntimeError('Backup contains an unsafe path.')
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with archive.open(info, 'r') as source, open(target, 'wb') as out:
            shutil.copyfileobj(source, out)


def _replace_tree(src: str, dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(dest):
        path = os.path.join(dest, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    if not os.path.isdir(src):
        return
    for name in os.listdir(src):
        source = os.path.join(src, name)
        target = os.path.join(dest, name)
        if os.path.isdir(source):
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def apply_restore(zip_path: str, parts: list[str], locations: dict, progress=None) -> dict:
    manifest = read_manifest(zip_path)
    requested = [part for part in parts if part in RESTORABLE and part in manifest['parts']]
    if not requested:
        raise RuntimeError('Nothing in this backup can be restored from the selected items.')
    prefixes = _prefixes_for(requested)
    extract_dir = zip_path + '.extract'
    if os.path.isdir(extract_dir):
        shutil.rmtree(extract_dir)
    try:
        _progress(progress, 'Reading backup')
        with zipfile.ZipFile(zip_path) as archive:
            _safe_extract(archive, extract_dir, prefixes)
        private = locations.get('private_root') or ''
        project = locations.get('project_root') or ''
        static_uploads = os.path.join(project, 'static', 'uploads')
        file_map = {
            'photos': [
                ('files/user_photos', os.path.join(private, 'user_photos')),
                ('files/legacy_static/user_photos', os.path.join(static_uploads, 'user_photos')),
            ],
            'signatures': [
                ('files/user_signatures', os.path.join(private, 'user_signatures')),
                ('files/legacy_static/user_signatures', os.path.join(static_uploads, 'user_signatures')),
            ],
            'admission': [
                ('files/admission_exam', os.path.join(private, 'admission_exam')),
                ('files/legacy_static/admission_exam', os.path.join(static_uploads, 'admission_exam')),
            ],
            'course_files': [
                ('files/course_uploads', os.path.join(project, 'uploads')),
            ],
        }
        for part, pairs in file_map.items():
            if part not in requested:
                continue
            _progress(progress, f'Restoring {part_label(part).lower()}')
            for arc, dest in pairs:
                src = os.path.join(extract_dir, *arc.split('/'))
                if os.path.isdir(src):
                    _replace_tree(src, dest)
        if 'settings' in requested:
            _progress(progress, 'Restoring saved settings')
            settings_dir = os.path.join(extract_dir, 'settings')
            instance_root = locations.get('instance_root') or ''
            os.makedirs(instance_root, exist_ok=True)
            if os.path.isdir(settings_dir):
                for name in os.listdir(settings_dir):
                    lower = name.lower()
                    if not (lower.startswith('academic_rules') or lower.startswith('remuneration_rates')):
                        continue
                    if not (lower.endswith('.yaml') or lower.endswith('.yml')):
                        continue
                    shutil.copy2(os.path.join(settings_dir, name), os.path.join(instance_root, name))
        if 'database' in requested:
            dump_path = os.path.join(extract_dir, 'database', 'dump.sql')
            if not os.path.isfile(dump_path):
                raise RuntimeError('The backup does not contain a database dump.')
            restore_database(locations['database_url'], dump_path, progress)
        return {'restored': requested}
    finally:
        if os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)


def _status_path(job_id: str) -> str:
    return os.path.join(backup_root(), job_id + '.json')


def _zip_path(job_id: str) -> str:
    return os.path.join(backup_root(), job_id + '.zip')


def write_status(job_id: str, payload: dict) -> None:
    path = _status_path(job_id)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)
    os.replace(tmp, path)


def read_status(job_id: str) -> dict | None:
    path = _status_path(job_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _lock_path() -> str:
    return os.path.join(backup_root(), '.lock')


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_lock() -> None:
    path = _lock_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                pid = int((handle.read() or '0').strip() or '0')
        except (OSError, ValueError):
            pid = 0
        stale = not _pid_alive(pid)
        try:
            age = datetime.utcnow().timestamp() - os.path.getmtime(path)
        except OSError:
            age = 999999
        if stale or age > 6 * 3600:
            try:
                os.remove(path)
            except OSError:
                pass
        else:
            raise RuntimeError('Another backup or restore is already running.')
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError('Another backup or restore is already running.') from exc
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)


def release_lock() -> None:
    try:
        os.remove(_lock_path())
    except OSError:
        pass


def locations_from_app(app) -> dict:
    from utils.private_uploads import get_private_upload_root

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    with app.app_context():
        return {
            'database_url': app.config['SQLALCHEMY_DATABASE_URI'],
            'private_root': get_private_upload_root(app),
            'project_root': project_root,
            'instance_root': app.instance_path,
        }


def start_backup(app, parts: list[str], kind: str = 'backup') -> str:
    selected = [part for part in parts if part in PART_KEYS]
    if not selected:
        raise RuntimeError('Choose at least one item to back up.')
    acquire_lock()
    job_id = uuid.uuid4().hex
    write_status(job_id, {
        'id': job_id,
        'state': 'running',
        'kind': kind,
        'message': 'Starting',
        'parts': selected,
    })
    worker = threading.Thread(
        target=_backup_worker,
        args=(app._get_current_object(), job_id, selected, kind),
        daemon=True,
    )
    worker.start()
    return job_id


def _backup_worker(app, job_id: str, parts: list[str], kind: str) -> None:
    try:
        with app.app_context():
            locs = locations_from_app(app)

            def progress(message):
                current = read_status(job_id) or {}
                current.update({'state': 'running', 'message': message})
                write_status(job_id, current)

            manifest = build_archive(_zip_path(job_id), parts, locs, progress, kind=kind)
            if kind == 'backup':
                _prune('backup', KEEP_BACKUPS)
            elif kind == 'safety':
                _prune('safety', KEEP_SAFETY)
            write_status(job_id, {
                'id': job_id,
                'state': 'done',
                'kind': kind,
                'message': 'Ready to download',
                'parts': manifest['parts'],
                'created_at': manifest['created_at'],
                'counts': manifest['counts'],
                'size': os.path.getsize(_zip_path(job_id)),
            })
    except Exception as exc:
        write_status(job_id, {
            'id': job_id,
            'state': 'error',
            'kind': kind,
            'message': str(exc) or 'Backup failed',
            'parts': parts,
        })
        try:
            os.remove(_zip_path(job_id))
        except OSError:
            pass
    finally:
        release_lock()


def start_restore(app, source_zip: str, parts: list[str]) -> str:
    if not os.path.isfile(source_zip):
        raise RuntimeError('Backup file was not found.')
    # Stay inside the backup directory.
    root = os.path.abspath(backup_root())
    full = os.path.abspath(source_zip)
    if not full.startswith(root + os.sep):
        raise RuntimeError('Backup file was not found.')
    manifest = read_manifest(full)
    selected = [part for part in parts if part in RESTORABLE and part in manifest['parts']]
    if not selected:
        raise RuntimeError('Choose at least one restorable item that this backup contains.')
    acquire_lock()
    job_id = uuid.uuid4().hex
    write_status(job_id, {
        'id': job_id,
        'state': 'running',
        'kind': 'restore',
        'message': 'Saving a safety copy first',
        'parts': selected,
    })
    worker = threading.Thread(
        target=_restore_worker,
        args=(app._get_current_object(), job_id, full, selected),
        daemon=True,
    )
    worker.start()
    return job_id


def _restore_worker(app, job_id: str, source_zip: str, parts: list[str]) -> None:
    safety_id = uuid.uuid4().hex
    try:
        with app.app_context():
            locs = locations_from_app(app)

            def progress(message):
                current = read_status(job_id) or {}
                current.update({'state': 'running', 'message': message})
                write_status(job_id, current)

            progress('Saving a safety copy of the current data')
            safety_manifest = build_archive(
                _zip_path(safety_id), parts, locs, progress, kind='safety',
            )
            write_status(safety_id, {
                'id': safety_id,
                'state': 'done',
                'kind': 'safety',
                'message': 'Safety copy kept before a restore',
                'parts': safety_manifest['parts'],
                'created_at': safety_manifest['created_at'],
                'size': os.path.getsize(_zip_path(safety_id)),
            })
            _prune('safety', KEEP_SAFETY)
            progress('Restoring')
            result = apply_restore(source_zip, parts, locs, progress)
            try:
                from extensions import db
                db.engine.dispose()
            except Exception:
                pass
            write_status(job_id, {
                'id': job_id,
                'state': 'done',
                'kind': 'restore',
                'message': 'Restore finished. Safety copy ' + safety_id,
                'parts': result['restored'],
                'safety_id': safety_id,
            })
    except Exception as exc:
        write_status(job_id, {
            'id': job_id,
            'state': 'error',
            'kind': 'restore',
            'message': str(exc) or 'Restore failed',
            'parts': parts,
            'safety_id': safety_id if os.path.isfile(_zip_path(safety_id)) else None,
        })
    finally:
        release_lock()


def list_archives() -> list[dict]:
    root = backup_root()
    rows = []
    seen = set()
    for name in os.listdir(root):
        if not name.endswith('.zip'):
            continue
        job_id = name[:-4]
        if not _safe_id(job_id) and not _safe_filename(name):
            continue
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        try:
            manifest = read_manifest(path)
        except Exception:
            continue
        status = read_status(job_id) or {}
        seen.add(job_id)
        rows.append({
            'id': job_id,
            'kind': status.get('kind') or manifest.get('kind') or 'backup',
            'state': 'done',
            'created_at': manifest.get('created_at') or '',
            'parts': manifest.get('parts') or [],
            'size': os.path.getsize(path),
            'message': status.get('message') or '',
        })
    for name in os.listdir(root):
        if not name.endswith('.json') or name.endswith('.tmp'):
            continue
        job_id = name[:-5]
        if job_id in seen or not _safe_id(job_id):
            continue
        status = read_status(job_id)
        if not status or status.get('state') not in ('running', 'error'):
            continue
        rows.append({
            'id': job_id,
            'kind': status.get('kind') or 'backup',
            'state': status.get('state'),
            'created_at': status.get('created_at') or '',
            'parts': status.get('parts') or [],
            'size': 0,
            'message': status.get('message') or '',
        })
    rows.sort(key=lambda row: row.get('created_at') or '', reverse=True)
    return rows


def _prune(kind: str, keep: int) -> None:
    rows = [row for row in list_archives() if row['kind'] == kind and row['state'] == 'done']
    rows.sort(key=lambda row: row.get('created_at') or '', reverse=True)
    for row in rows[keep:]:
        delete_archive(row['id'])


def delete_archive(job_id: str) -> None:
    if not _safe_id(job_id):
        raise RuntimeError('Unknown backup.')
    for path in (_zip_path(job_id), _status_path(job_id)):
        try:
            os.remove(path)
        except OSError:
            pass


def resolve_zip(job_id: str) -> str:
    if not _safe_id(job_id):
        raise RuntimeError('Unknown backup.')
    path = os.path.abspath(_zip_path(job_id))
    root = os.path.abspath(backup_root())
    if not path.startswith(root + os.sep) or not os.path.isfile(path):
        raise RuntimeError('Backup file was not found.')
    return path


def _safe_id(value: str) -> bool:
    return bool(value) and len(value) <= 80 and all(ch.isalnum() or ch in '._-' for ch in value)


def _safe_filename(name: str) -> bool:
    return _safe_id(name[:-4]) if name.endswith('.zip') else False


def store_uploaded_zip(stream, original_name: str) -> str:
    job_id = uuid.uuid4().hex
    path = _zip_path(job_id)
    tmp = path + '.partial'
    try:
        with open(tmp, 'wb') as handle:
            shutil.copyfileobj(stream, handle)
        manifest = read_manifest(tmp)
        os.replace(tmp, path)
        write_status(job_id, {
            'id': job_id,
            'state': 'done',
            'kind': 'upload',
            'message': 'Uploaded ' + os.path.basename(original_name or 'backup.zip'),
            'parts': manifest['parts'],
            'created_at': manifest.get('created_at') or datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'size': os.path.getsize(path),
        })
        return job_id
    except Exception:
        for candidate in (tmp, path):
            try:
                os.remove(candidate)
            except OSError:
                pass
        raise

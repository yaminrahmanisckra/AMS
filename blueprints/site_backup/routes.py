"""Admin-only backup download and restore."""
from __future__ import annotations

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from role_utils import has_stored_admin, is_admin
from utils.audit import write_audit
from utils.site_backup import (
    PARTS,
    RESTORABLE,
    RESTORE_PHRASE,
    backup_root,
    delete_archive,
    describe_parts,
    format_size,
    list_archives,
    locations_from_app,
    read_status,
    resolve_zip,
    start_backup,
    start_restore,
    store_uploaded_zip,
)

from . import site_backup_bp

_UPLOAD_LIMIT = 1024 * 1024 * 1024


def _install_upload_limit(state):
    """Allow a large restore zip on this route only. The app default is 16 MB."""
    app = state.app
    base = app.request_class
    if getattr(base, '_ams_backup_upload', False):
        return

    class Request(base):
        _ams_backup_upload = True

        @property
        def max_content_length(self):
            path = (self.path or '').rstrip('/')
            if path == '/admin/backup/upload':
                return _UPLOAD_LIMIT
            return super().max_content_length

    app.request_class = Request


site_backup_bp.record(_install_upload_limit)


def _require_admin():
    if not current_user.is_authenticated or not is_admin(current_user) or not has_stored_admin(current_user):
        flash('Only the administrator account can back up or restore the site.', 'danger')
        return redirect(url_for('index'))
    return None


@site_backup_bp.route('/')
@login_required
def index():
    denied = _require_admin()
    if denied:
        return denied
    locs = locations_from_app(current_app)
    parts = describe_parts(locs['private_root'], locs['project_root'], locs['instance_root'])
    for row in parts:
        row['size_label'] = format_size(row['size']) if row['key'] != 'database' else 'MySQL / SQLite'
        if row['key'] == 'code':
            row['size_label'] = 'Program files'
    return render_template(
        'site_backup/backup.html',
        parts=parts,
        archives=list_archives(),
        backup_dir=backup_root(),
        job_id=(request.args.get('job') or '').strip(),
        format_size=format_size,
        restorable=RESTORABLE,
    )


@site_backup_bp.route('/start', methods=['POST'])
@login_required
def start():
    denied = _require_admin()
    if denied:
        return denied
    selected = [key for key, _label, _help in PARTS if request.form.get('part_' + key) == '1']
    if request.form.get('everything') == '1':
        selected = [key for key, _label, _help in PARTS]
    try:
        job_id = start_backup(current_app, selected)
    except Exception as exc:
        write_audit('site_backup_failed', 'backup', extra={'error': str(exc)})
        if _wants_json():
            return jsonify({'ok': False, 'error': str(exc)}), 400
        flash(str(exc), 'danger')
        return redirect(url_for('site_backup.index'))
    write_audit('site_backup_started', 'backup', entity_id=job_id, extra={'parts': selected})
    if _wants_json():
        return jsonify({'ok': True, 'job_id': job_id})
    return redirect(url_for('site_backup.index', job=job_id))


@site_backup_bp.route('/status/<job_id>')
@login_required
def status(job_id):
    denied = _require_admin()
    if denied:
        return denied
    payload = read_status(job_id)
    if not payload:
        return jsonify({'ok': False, 'error': 'Not found'}), 404
    payload['ok'] = True
    if payload.get('size'):
        payload['size_label'] = format_size(payload['size'])
    return jsonify(payload)


@site_backup_bp.route('/download/<job_id>')
@login_required
def download(job_id):
    denied = _require_admin()
    if denied:
        return denied
    try:
        path = resolve_zip(job_id)
    except Exception as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('site_backup.index'))
    write_audit('site_backup_download', 'backup', entity_id=job_id)
    return send_file(
        path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'ams-backup-{job_id[:8]}.zip',
        conditional=True,
        max_age=0,
    )


@site_backup_bp.route('/restore', methods=['POST'])
@login_required
def restore():
    denied = _require_admin()
    if denied:
        return denied
    if (request.form.get('confirm') or '').strip() != RESTORE_PHRASE:
        flash('Type RESTORE to confirm. Nothing was changed.', 'warning')
        return redirect(url_for('site_backup.index'))
    job_id = (request.form.get('archive_id') or '').strip()
    selected = [part for part in RESTORABLE if request.form.get('restore_' + part) == '1']
    try:
        source = resolve_zip(job_id)
        restore_id = start_restore(current_app, source, selected)
    except Exception as exc:
        write_audit('site_restore_failed', 'backup', entity_id=job_id, extra={'error': str(exc)})
        flash(str(exc), 'danger')
        return redirect(url_for('site_backup.index'))
    write_audit('site_restore_started', 'backup', entity_id=restore_id, extra={
        'source': job_id,
        'parts': selected,
    })
    flash('Restore started. A safety copy of the current data is saved first.', 'info')
    return redirect(url_for('site_backup.index', job=restore_id))


@site_backup_bp.route('/upload', methods=['POST'])
@login_required
def restore_upload():
    denied = _require_admin()
    if denied:
        return denied
    if (request.form.get('confirm') or '').strip() != RESTORE_PHRASE:
        flash('Type RESTORE to confirm. Nothing was changed.', 'warning')
        return redirect(url_for('site_backup.index'))
    upload = request.files.get('archive')
    if not upload or not upload.filename:
        flash('Choose the backup zip to restore.', 'warning')
        return redirect(url_for('site_backup.index'))
    selected = [part for part in RESTORABLE if request.form.get('restore_' + part) == '1']
    try:
        stored_id = store_uploaded_zip(upload.stream, upload.filename)
        source = resolve_zip(stored_id)
        restore_id = start_restore(current_app, source, selected)
    except Exception as exc:
        write_audit('site_restore_failed', 'backup', extra={'error': str(exc)})
        flash(str(exc), 'danger')
        return redirect(url_for('site_backup.index'))
    write_audit('site_restore_started', 'backup', entity_id=restore_id, extra={
        'source': stored_id,
        'parts': selected,
        'uploaded': True,
    })
    flash('Uploaded backup accepted. Restore started after a safety copy.', 'info')
    return redirect(url_for('site_backup.index', job=restore_id))


@site_backup_bp.route('/delete/<job_id>', methods=['POST'])
@login_required
def delete(job_id):
    denied = _require_admin()
    if denied:
        return denied
    status = read_status(job_id) or {}
    if status.get('state') == 'running':
        flash('That job is still running.', 'warning')
        return redirect(url_for('site_backup.index'))
    try:
        delete_archive(job_id)
    except Exception as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('site_backup.index'))
    write_audit('site_backup_deleted', 'backup', entity_id=job_id)
    flash('Backup removed from the server.', 'success')
    return redirect(url_for('site_backup.index'))


def _wants_json() -> bool:
    return 'application/json' in (request.headers.get('Accept') or '')

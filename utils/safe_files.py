"""Serve only files that live under allowed upload directories (static + private)."""
from __future__ import annotations

import os

from flask import abort, current_app, send_file


def _realpath(path):
    return os.path.realpath(os.path.abspath(path))


def upload_roots(app=None):
    """Directories that may contain user/staff uploaded files."""
    app = app or current_app
    root = app.root_path
    static = app.static_folder or os.path.join(root, 'static')
    cwd = os.getcwd()
    parent = os.path.dirname(root)
    candidates = [
        os.path.join(static, 'uploads'),
        os.path.join(root, 'uploads'),
        os.path.join(root, 'instance', 'uploads'),
        os.path.join(cwd, 'uploads'),
        os.path.join(cwd, 'static', 'uploads'),
        os.path.join(parent, 'static', 'uploads'),
        os.path.join(parent, 'uploads'),
    ]
    try:
        from utils.private_uploads import get_private_upload_root
        candidates.insert(0, get_private_upload_root(app))
    except Exception:
        pass
    roots = []
    seen = set()
    for item in candidates:
        try:
            real = _realpath(item)
        except (OSError, ValueError):
            continue
        if real not in seen:
            seen.add(real)
            roots.append(real)
    return roots


def is_under_upload_root(path, app=None):
    if not path:
        return False
    real = _realpath(path)
    for root in upload_roots(app):
        prefix = root if root.endswith(os.sep) else root + os.sep
        if real == root or real.startswith(prefix):
            return True
    return False


def confined_existing_file(stored_path, app=None):
    """Absolute path if the stored value points at a real file inside upload roots."""
    if not stored_path:
        return None
    app = app or current_app
    raw = str(stored_path).strip().replace('\\', '/')
    if not raw or raw in ('.', '..') or '\x00' in raw:
        return None

    root = app.root_path
    static = app.static_folder or os.path.join(root, 'static')
    under_static = raw[7:] if raw.startswith('static/') else raw.lstrip('/')
    candidates = []
    if os.path.isabs(raw) or (len(raw) > 2 and raw[1] == ':'):
        candidates.append(raw)
    candidates.extend([
        os.path.join(root, raw.lstrip('/')),
        os.path.join(static, under_static),
        os.path.join(os.path.dirname(root), raw.lstrip('/')),
        os.path.join(os.getcwd(), raw.lstrip('/')),
        os.path.join(os.getcwd(), 'static', under_static),
    ])

    # Dual-read: private root (new layout + copied legacy basenames).
    try:
        from utils.private_uploads import get_private_upload_root, legacy_static_prefix_to_relative
        private_root = get_private_upload_root(app)
        rel = legacy_static_prefix_to_relative(raw)
        if rel:
            candidates.append(os.path.join(private_root, *rel.split('/')))
        # Also try raw as already-private relative path (user_photos/…)
        stripped = raw.lstrip('/')
        if not stripped.startswith('static/'):
            candidates.append(os.path.join(private_root, *stripped.split('/')))
    except Exception:
        pass

    for candidate in candidates:
        if not candidate:
            continue
        try:
            if not os.path.isfile(candidate):
                continue
        except (OSError, ValueError):
            continue
        if is_under_upload_root(candidate, app):
            return _realpath(candidate)
    return None


def send_confined_file(stored_path, **kwargs):
    """send_file after confinement; 404 if the path is missing or outside uploads.

    Always sets ``X-Content-Type-Options: nosniff``. When ``as_attachment`` is
    true (default for ``download_name`` alone is left to Flask), attachment
    disposition is preferred for untrusted user uploads.
    """
    path = confined_existing_file(stored_path)
    if not path:
        abort(404)
    force_attachment = kwargs.pop('force_attachment', None)
    if force_attachment:
        kwargs['as_attachment'] = True
    download_name = kwargs.get('download_name')
    if download_name:
        from utils.email_safety import safe_download_filename
        kwargs['download_name'] = safe_download_filename(download_name)
    response = send_file(path, **kwargs)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    if kwargs.get('as_attachment') or force_attachment:
        from utils.uploads import apply_download_headers
        from utils.email_safety import content_disposition_attachment
        apply_download_headers(response, as_attachment=True)
        # Prefer RFC 5987 disposition when we have a download name
        name = kwargs.get('download_name')
        if name:
            response.headers['Content-Disposition'] = content_disposition_attachment(name)
    else:
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    return response

"""Serve only files that live under the app's upload directories."""
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
    roots = []
    seen = set()
    for item in candidates:
        real = _realpath(item)
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
    """send_file after confinement; 404 if the path is missing or outside uploads."""
    path = confined_existing_file(stored_path)
    if not path:
        abort(404)
    return send_file(path, **kwargs)

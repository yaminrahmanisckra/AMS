"""Private upload root (outside docroot) for photos, signatures, admission files.

AUTHZ / FILE-01, FILE-02: new files are written under ``PRIVATE_UPLOAD_DIR``
(default ``~/ams_private_uploads``). Stored DB values are opaque relative paths
such as ``user_photos/<token>.jpg`` — never public ``/static/uploads/...`` URLs.
Legacy ``static/uploads/...`` paths remain readable via dual-root resolution in
``utils.safe_files``.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename


PRIVATE_SUBDIRS = (
    'user_photos',
    'user_signatures',
    'admission_exam',
)


def default_private_upload_dir() -> str:
    home = os.path.expanduser('~')
    return os.path.join(home, 'ams_private_uploads')


def get_private_upload_root(app=None) -> str:
    """Absolute private upload root (created if missing)."""
    app = app or current_app
    configured = (app.config.get('PRIVATE_UPLOAD_DIR') or os.environ.get('PRIVATE_UPLOAD_DIR') or '').strip()
    root = os.path.expanduser(configured) if configured else default_private_upload_dir()
    root = os.path.realpath(os.path.abspath(root))
    os.makedirs(root, exist_ok=True)
    for sub in PRIVATE_SUBDIRS:
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    return root


def ensure_private_subdir(*parts, app=None) -> str:
    """Create and return an absolute subdirectory under the private root."""
    root = get_private_upload_root(app)
    path = os.path.join(root, *[str(p) for p in parts if p is not None and str(p) != ''])
    os.makedirs(path, exist_ok=True)
    return path


def private_token_filename(ext: str) -> str:
    """Opaque filename: ``<token_urlsafe(16)>.<ext>``."""
    clean_ext = (ext or '').lstrip('.').lower()
    if not clean_ext:
        clean_ext = 'bin'
    clean_ext = secure_filename(clean_ext) or 'bin'
    return f'{secrets.token_urlsafe(16)}.{clean_ext}'


def store_relative(*parts) -> str:
    """POSIX-style relative path for DB storage (no leading slash)."""
    cleaned = []
    for part in parts:
        if part is None:
            continue
        text = str(part).replace('\\', '/').strip('/')
        if text:
            cleaned.append(text)
    return '/'.join(cleaned)


def legacy_static_prefix_to_relative(stored_path: str | None) -> str | None:
    """Map ``/static/uploads/X`` or ``static/uploads/X`` → ``X`` for private dual-read."""
    if not stored_path:
        return None
    raw = str(stored_path).strip().replace('\\', '/').lstrip('/')
    for prefix in ('static/uploads/', 'uploads/'):
        if raw.startswith(prefix):
            return raw[len(prefix):]
    return raw or None


def abs_under_private(relative_path: str, app=None) -> str:
    """Join private root with a relative path (does not check existence)."""
    rel = str(relative_path).replace('\\', '/').lstrip('/')
    return os.path.join(get_private_upload_root(app), *rel.split('/'))


def save_bytes_private(data: bytes, *subdir_and_name, app=None) -> str:
    """Write bytes under private root; return relative store path."""
    if not subdir_and_name:
        raise ValueError('subdir and filename required')
    *dirs, filename = subdir_and_name
    folder = ensure_private_subdir(*dirs, app=app)
    abs_path = os.path.join(folder, filename)
    Path(abs_path).write_bytes(data)
    return store_relative(*dirs, filename)

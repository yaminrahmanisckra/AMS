"""Shared user signature helpers (profile, admission, remuneration PDFs).

Signatures are stored on ``User.signature_path`` under
``static/uploads/user_signatures/`` and reused wherever a staff/teacher
signature image is needed.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_SIGNATURE_EXTS = frozenset({'png', 'jpg', 'jpeg'})
SIGNATURE_MAX_UPLOAD_BYTES = 1 * 1024 * 1024
SIGNATURE_MAX_SIZE_LABEL = '1 MB'
SIGNATURE_MAX_DIMENSIONS = (800, 300)


def resolve_upload_path(relative_path):
    """Resolve a stored path only if it stays under the app upload roots."""
    from utils.safe_files import confined_existing_file
    return confined_existing_file(relative_path)


def user_signature_abs_path(user):
    """Absolute filesystem path for ``user.signature_path``, or None."""
    if not user:
        return None
    return resolve_upload_path(getattr(user, 'signature_path', None))


def user_signature_public_url(user):
    """URL path for preview (``/static/uploads/...``), or None."""
    if not user or not getattr(user, 'signature_path', None):
        return None
    rel = str(user.signature_path).replace('\\', '/').lstrip('/')
    if not rel.startswith('static/'):
        rel = f'static/{rel}'
    return '/' + rel


def save_user_signature(user, file_storage):
    """Save JPG/PNG signature for ``user``. Returns ``(relative_path, error)``."""
    filename = secure_filename(file_storage.filename or '')
    if not filename or '.' not in filename:
        return None, 'Invalid signature file.'
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_SIGNATURE_EXTS:
        return None, 'Signature must be a JPG or PNG image.'
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        return None, 'Signature file is empty.'
    if size > SIGNATURE_MAX_UPLOAD_BYTES:
        return None, f'Signature is too large. Maximum is {SIGNATURE_MAX_SIZE_LABEL}.'
    try:
        from PIL import Image, ImageOps

        img = Image.open(file_storage.stream)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        keep_alpha = img.mode in ('RGBA', 'LA') or (
            img.mode == 'P' and 'transparency' in img.info
        )
        if keep_alpha:
            img = img.convert('RGBA')
            out_ext = 'png'
        else:
            img = img.convert('RGB')
            out_ext = 'jpg'
        resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.LANCZOS)
        img.thumbnail(SIGNATURE_MAX_DIMENSIONS, resample)
        folder = os.path.join(current_app.root_path, 'static', 'uploads', 'user_signatures')
        os.makedirs(folder, exist_ok=True)
        new_name = f'user_{user.id}_sig_{int(datetime.utcnow().timestamp())}.{out_ext}'
        abs_path = os.path.join(folder, new_name)
        if out_ext == 'png':
            img.save(abs_path, format='PNG', optimize=True)
        else:
            img.save(abs_path, format='JPEG', quality=90, optimize=True)
        return os.path.join('static', 'uploads', 'user_signatures', new_name).replace('\\', '/'), None
    except Exception:
        current_app.logger.exception('User signature save failed')
        return None, 'Could not read the signature image. Please upload a valid JPG or PNG.'


def delete_user_signature_file(user):
    """Remove the on-disk signature file if present (does not clear DB field)."""
    path = user_signature_abs_path(user)
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        current_app.logger.warning('Could not delete signature file %s', path)


def user_signature_data_uri(user):
    """Base64 data URI for WeasyPrint embedding, or None."""
    path = user_signature_abs_path(user)
    if not path:
        return None
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
        if not raw:
            return None
        ext = path.rsplit('.', 1)[-1].lower()
        mime = 'image/png' if ext == 'png' else 'image/jpeg'
        return f'data:{mime};base64,{base64.b64encode(raw).decode("ascii")}'
    except Exception:
        current_app.logger.exception('Could not build signature data URI for user %s', getattr(user, 'id', None))
        return None


def find_user_for_signature_by_name(full_name):
    """Best-effort User lookup by full_name (for PDF recipient / officers)."""
    name = (full_name or '').strip()
    if not name:
        return None
    try:
        from user_models import User
    except Exception:
        return None
    user = User.query.filter(User.full_name == name).first()
    if user:
        return user
    # Soft match: ignore extra spaces / case
    normalized = ' '.join(name.lower().split())
    for u in User.query.filter(User.signature_path.isnot(None)).limit(500).all():
        if ' '.join((u.full_name or '').lower().split()) == normalized:
            return u
    return None


def signature_data_uri_for_name(full_name):
    """Data URI for the user matching ``full_name``, or None."""
    return user_signature_data_uri(find_user_for_signature_by_name(full_name))


def find_user_for_teacher(teacher):
    """Resolve a Teacher record to its linked User account."""
    if not teacher:
        return None
    try:
        from user_models import User
    except Exception:
        return None
    user = User.query.filter_by(teacher_id=teacher.id).first()
    if user:
        return user
    name = (getattr(teacher, 'name', None) or '').strip()
    if name:
        user = User.query.filter(User.full_name == name).first()
        if user:
            return user
        return find_user_for_signature_by_name(name)
    return None


def find_head_user():
    """First user with head role; prefer one that has an uploaded signature."""
    try:
        from user_models import User
        from role_utils import parse_roles
    except Exception:
        return None
    heads = []
    for user in User.query.all():
        if 'head' in parse_roles(getattr(user, 'role', None)):
            heads.append(user)
    if not heads:
        return None
    for user in heads:
        if getattr(user, 'signature_path', None):
            return user
    return heads[0]


def _resolve_signature_user(user_or_name):
    """Accept User, Teacher, or full_name string."""
    if not user_or_name:
        return None
    if isinstance(user_or_name, str):
        return find_user_for_signature_by_name(user_or_name)
    try:
        from user_models import User
        if isinstance(user_or_name, User):
            return user_or_name
    except Exception:
        pass
    return find_user_for_teacher(user_or_name)


def reportlab_signature_flowable(user_or_name, max_width, max_height):
    """ReportLab Image flowable for a profile signature, or empty Spacer."""
    from reportlab.platypus import Image as RLImage, Spacer

    user = _resolve_signature_user(user_or_name)
    path = user_signature_abs_path(user)
    if not path:
        return Spacer(max_width, max_height * 0.5)
    try:
        return RLImage(path, width=max_width, height=max_height, kind='proportional')
    except Exception:
        current_app.logger.warning(
            'Could not embed signature for %s',
            getattr(user, 'id', user_or_name),
            exc_info=True,
        )
        return Spacer(max_width, max_height * 0.5)

"""Admission Exam routes.

Public side (token URL, no Flask-Login): candidate registration, Application
ID + PIN login, dashboard, admit card download.

Committee/admin side (Flask-Login): cycle management, payment verification,
selection, roll assignment, admit publishing, candidate management.
"""
import io
import json
import os
import re
import secrets
import tempfile
import uuid
import base64
from datetime import datetime
from functools import wraps
from html.parser import HTMLParser
from markupsafe import Markup, escape
from utils.timezone import format_bd
from utils.tenant import current_tenant, public_app_url

from flask import (
    render_template, redirect, url_for, flash, request, session,
    current_app, send_file, abort, jsonify, make_response
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db, csrf
from role_utils import is_admin, has_role, parse_roles

from . import admission_exam_bp
from .models import (
    AdmissionCycle, AdmissionCommitteeMember, AdmissionCandidate,
    AdmissionCandidateDocument,
)
from .fields import (
    get_field_schema, serialize_field_schema, parse_schema_from_form,
    fields_where, form_input_fields, extra_field_defs, personal_extra_field_defs,
    parse_extra_fields, collect_extra_fields, candidate_field_value,
    default_field_schema, PAYMENT_METHOD_LABELS, PAYMENT_FIELD_KEYS,
    PAYMENT_METHOD_ORDER, MFS_PAYMENT_METHODS, DEFAULT_PAYMENT_METHOD,
    is_mfs_payment_method, mfs_field_labels,
    ACADEMIC_EXAM_ROWS, ACADEMIC_COL_SUFFIXES, ACADEMIC_FIELD_KEYS,
    academic_form_enabled, FILE_FIELD_KEYS,
    parse_academic_extra_rows, academic_display_rows, collect_academic_extra_rows,
    get_document_tags, serialize_document_tags, normalize_document_tags,
    DOCUMENT_STATUSES, DOCUMENT_ALLOWED_EXTS, DOCUMENT_MAX_BYTES, DOCUMENT_MAX_LABEL,
    get_declaration_text, serialize_declaration_text, default_declaration_text,
)
from user_models import User

ALLOWED_PHOTO_EXTS = {'png', 'jpg', 'jpeg'}
# Passport photo: reject uploads over 1 MB; store resized JPEG (~50–150 KB typical).
PHOTO_MAX_UPLOAD_BYTES = 1 * 1024 * 1024
PHOTO_MAX_SIZE_LABEL = '1 MB'
PHOTO_MAX_DIMENSIONS = (600, 750)  # width × height — enough for admit-card print
PHOTO_JPEG_QUALITY = 85
CANDIDATE_SESSION_KEY = 'admission_candidate_id'

# Bump this when admit-card PDF code changes. Visible in PDF title/footer + HTTP header.
ADMIT_PDF_ENGINE = 'WEASY-STAMP-6'
# Application-form PDF engine (Weasy+stamp). Appears in download filename.
APP_FORM_PDF_ENGINE = 'APP-WEASY-3'

PAYMENT_STATUSES = ('pending', 'verified', 'rejected')
APPLICATION_STATUSES = ('submitted', 'selected', 'rejected')
CYCLE_STATUSES = ('draft', 'open', 'closed')
BANK_SLIP_MAX_UPLOAD_BYTES = 2 * 1024 * 1024
BANK_SLIP_MAX_SIZE_LABEL = '2 MB'
BANK_SLIP_MAX_DIMENSIONS = (1600, 1600)

LANDING_FILE_MAX_BYTES = 10 * 1024 * 1024
LANDING_FILE_MAX_LABEL = '10 MB'
LANDING_FILE_EXTS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'txt', 'zip', 'rar',
}
_LANDING_HTML_ALLOWED = {
    'p', 'br', 'div', 'span', 'strong', 'b', 'em', 'i', 'u', 's', 'sub', 'sup',
    'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'blockquote', 'hr',
}
_LANDING_HTML_VOID = {'br', 'hr'}
_LANDING_STYLE_SAFE = re.compile(
    r'^(?:\s*(?:font-size|font-weight|font-style|text-decoration|text-align)\s*:\s*[^;]+;?\s*)+$',
    re.I,
)

# Backward-compatible alias (legacy templates / exports). Prefer extra_field_defs(cycle).
EXTRA_FIELD_DEFS = [
    (f['key'], f['label']) for f in default_field_schema() if f.get('source') == 'extra'
]


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

def _user_is_manager():
    """Admins and officers can create cycles and manage everything."""
    return current_user.is_authenticated and (is_admin(current_user) or has_role(current_user, 'officer'))


def _user_committee_cycle_ids():
    if not current_user.is_authenticated:
        return []
    rows = AdmissionCommitteeMember.query.filter_by(user_id=current_user.id).all()
    return [r.cycle_id for r in rows]


def _can_access_cycle(cycle):
    if _user_is_manager():
        return True
    return cycle.id in _user_committee_cycle_ids()


def user_can_access_admission():
    """Used by the dashboard to decide whether to show the module card."""
    if not current_user.is_authenticated:
        return False
    if _user_is_manager():
        return True
    return AdmissionCommitteeMember.query.filter_by(user_id=current_user.id).count() > 0


def cycle_access_required(view):
    """Load cycle by id kwarg and enforce committee/admin access."""
    @wraps(view)
    def wrapped(cycle_id, *args, **kwargs):
        cycle = AdmissionCycle.query.get_or_404(cycle_id)
        if not _can_access_cycle(cycle):
            flash('You do not have access to this admission cycle.', 'danger')
            abort(403)
        return view(cycle, *args, **kwargs)
    return wrapped


def candidate_access_required(view):
    """Load candidate by id kwarg and enforce access via its cycle."""
    @wraps(view)
    def wrapped(candidate_id, *args, **kwargs):
        candidate = AdmissionCandidate.query.get_or_404(candidate_id)
        if not _can_access_cycle(candidate.cycle):
            flash('You do not have access to this admission cycle.', 'danger')
            abort(403)
        return view(candidate, *args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Candidate session helpers (separate from Flask-Login)
# ---------------------------------------------------------------------------

def _current_candidate(token):
    cid = session.get(CANDIDATE_SESSION_KEY)
    if not cid:
        return None
    candidate = AdmissionCandidate.query.get(cid)
    if not candidate or not candidate.cycle or candidate.cycle.public_token != token:
        return None
    return candidate


def _cycle_disabled_response(cycle):
    return render_template('admission_exam/cycle_disabled.html', cycle=cycle), 403


def _public_cycle_by_token(token):
    """Load cycle for public routes; return (cycle, error_response)."""
    cycle = AdmissionCycle.query.filter_by(public_token=token).first_or_404()
    if not cycle.is_cycle_enabled:
        return cycle, _cycle_disabled_response(cycle)
    return cycle, None


def candidate_required(view):
    @wraps(view)
    def wrapped(token, *args, **kwargs):
        cycle, disabled = _public_cycle_by_token(token)
        if disabled:
            return disabled
        candidate = _current_candidate(token)
        if not candidate:
            return redirect(url_for('admission_exam.candidate_login', token=token))
        return view(cycle, candidate, *args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def _normalize_slug(value):
    """Short public link slug: lowercase letters, digits, hyphens (e.g. llm2027)."""
    value = (value or '').strip().lower()
    value = re.sub(r'[^a-z0-9-]+', '-', value)
    value = re.sub(r'-{2,}', '-', value).strip('-')
    return value[:64]


def _slug_available(slug, exclude_cycle_id=None):
    if not slug or len(slug) < 3:
        return False
    q = AdmissionCycle.query.filter_by(public_token=slug)
    if exclude_cycle_id:
        q = q.filter(AdmissionCycle.id != exclude_cycle_id)
    return q.first() is None


def _default_slug_from_prefix(prefix):
    """Suggest llm2027-style slug from application ID prefix + current year."""
    base = _normalize_slug(prefix) or 'admission'
    year = datetime.utcnow().year
    candidate = f"{base}{year}"
    if _slug_available(candidate):
        return candidate
    n = 2
    while not _slug_available(f"{candidate}-{n}"):
        n += 1
    return f"{candidate}-{n}"


def _user_is_committee_eligible(user):
    """Teachers and officers only (exam committee dropdown)."""
    return bool(set(parse_roles(getattr(user, 'role', None))) & {'teacher', 'officer'})


def _committee_eligible_users():
    return [u for u in User.query.order_by(User.full_name).all() if _user_is_committee_eligible(u)]


def _generate_pin():
    return f"{secrets.randbelow(1000000):06d}"


def _generate_application_id(cycle):
    prefix = (cycle.app_id_prefix or 'APP').strip().upper() or 'APP'
    n = cycle.candidates.count() + 1
    while True:
        app_id = f"{prefix}-{n:04d}"
        if not AdmissionCandidate.query.filter_by(application_id=app_id).first():
            return app_id
        n += 1


def _photo_dir(cycle):
    """Prefer static/uploads (same pattern as user photos — reliable on cPanel)."""
    path = os.path.join(
        current_app.root_path, 'static', 'uploads', 'admission_exam', f'cycle_{cycle.id}'
    )
    os.makedirs(path, exist_ok=True)
    return path


def _save_image_upload(cycle, application_id, file_storage, *, kind='photo',
                       max_bytes=PHOTO_MAX_UPLOAD_BYTES, max_label=PHOTO_MAX_SIZE_LABEL,
                       max_dims=PHOTO_MAX_DIMENSIONS):
    """Validate/resize an image upload. Returns (relative_path, error)."""
    filename = secure_filename(file_storage.filename or '')
    if not filename or '.' not in filename:
        return None, f'Invalid {kind} file.'
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_PHOTO_EXTS:
        return None, f'{kind.capitalize()} must be a JPG or PNG image.'

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        return None, f'{kind.capitalize()} file is empty.'
    if size > max_bytes:
        return None, (
            f'{kind.capitalize()} is too large ({size / (1024 * 1024):.1f} MB). '
            f'Maximum allowed size is {max_label}. '
            'Compress or resize the image and try again.'
        )

    try:
        from PIL import Image, ImageOps
        img = Image.open(file_storage.stream)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.LANCZOS)
        img.thumbnail(max_dims, resample)
    except Exception:
        return None, f'Could not read the {kind}. Please upload a valid JPG or PNG image.'

    safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', application_id)
    if kind == 'bank slip':
        prefix = 'slip'
    elif kind == 'signature':
        prefix = 'sig'
    else:
        prefix = 'photo'
    new_name = f"{safe_id}_{prefix}_{int(datetime.utcnow().timestamp())}.jpg"
    abs_path = os.path.join(_photo_dir(cycle), new_name)
    img.save(abs_path, format='JPEG', quality=PHOTO_JPEG_QUALITY, optimize=True)
    return os.path.join('static', 'uploads', 'admission_exam', f'cycle_{cycle.id}', new_name), None


def _save_photo(cycle, application_id, file_storage):
    """Validate size, resize to passport dimensions, save as JPEG. Returns (path, error)."""
    return _save_image_upload(
        cycle, application_id, file_storage, kind='photo',
        max_bytes=PHOTO_MAX_UPLOAD_BYTES, max_label=PHOTO_MAX_SIZE_LABEL,
        max_dims=PHOTO_MAX_DIMENSIONS,
    )


def _save_bank_slip(cycle, application_id, file_storage):
    """Save Agrani Bank deposit-slip photo. Returns (path, error)."""
    return _save_image_upload(
        cycle, application_id, file_storage, kind='bank slip',
        max_bytes=BANK_SLIP_MAX_UPLOAD_BYTES, max_label=BANK_SLIP_MAX_SIZE_LABEL,
        max_dims=BANK_SLIP_MAX_DIMENSIONS,
    )


def _save_candidate_signature(cycle, application_id, file_storage):
    """Save applicant signature (PNG/JPG). Returns (relative_path, error)."""
    return _save_image_upload(
        cycle, application_id, file_storage, kind='signature',
        max_bytes=PHOTO_MAX_UPLOAD_BYTES, max_label=PHOTO_MAX_SIZE_LABEL,
        max_dims=(800, 300),
    )


def _save_candidate_document(cycle, application_id, file_storage):
    """Save attested certificate/transcript (JPG/PNG only, max 5 MB). Returns (path, orig_name, err)."""
    filename = secure_filename(file_storage.filename or '')
    if not filename or '.' not in filename:
        return None, None, 'Invalid document file.'
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in DOCUMENT_ALLOWED_EXTS:
        return None, None, 'Documents must be JPG or PNG images (PDF is not allowed).'
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        return None, None, 'Document file is empty.'
    if size > DOCUMENT_MAX_BYTES:
        return None, None, (
            f'Document is too large ({size / (1024 * 1024):.1f} MB). '
            f'Maximum allowed size is {DOCUMENT_MAX_LABEL}.'
        )
    safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', application_id)
    new_name = f"{safe_id}_doc_{uuid.uuid4().hex[:10]}.{ext}"
    abs_path = os.path.join(_photo_dir(cycle), new_name)
    file_storage.save(abs_path)
    rel = os.path.join('static', 'uploads', 'admission_exam', f'cycle_{cycle.id}', new_name)
    return rel.replace('\\', '/'), filename[:255], None


def _document_abs_path(document):
    return _resolve_upload_path(getattr(document, 'file_path', None) if document else None)


def _collect_document_uploads(cycle, application_id, form, files):
    """Parse tagged document uploads from apply/dashboard form.

    Expects parallel lists: doc_tag[], doc_tag_custom[], and files doc_file.
    Returns (list_of_{tag,path,original_filename}, error_message).
    """
    tags = form.getlist('doc_tag') if hasattr(form, 'getlist') else []
    customs = form.getlist('doc_tag_custom') if hasattr(form, 'getlist') else []
    file_list = files.getlist('doc_file') if hasattr(files, 'getlist') else []
    if not file_list and files.get('doc_file'):
        file_list = [files.get('doc_file')]

    saved = []
    n = max(len(tags), len(customs), len(file_list))
    for i in range(n):
        f = file_list[i] if i < len(file_list) else None
        if not f or not getattr(f, 'filename', None):
            continue
        tag = (tags[i] if i < len(tags) else '').strip()
        custom = (customs[i] if i < len(customs) else '').strip()
        if tag == '__custom__' or not tag:
            tag = custom
        tag = (tag or '').strip()[:120]
        if not tag:
            return None, 'Please choose or type a tag for each uploaded document.'
        path, orig, err = _save_candidate_document(cycle, application_id, f)
        if err:
            return None, err
        saved.append({'tag': tag, 'file_path': path, 'original_filename': orig})
    return saved, None


def _save_user_signature(user, file_storage):
    """Save teacher/officer signature (shared with profile / remuneration)."""
    from utils.user_signature import save_user_signature
    return save_user_signature(user, file_storage)


def _normalize_payment_method(value, cycle=None):
    method = (value or '').strip().lower()
    if method not in PAYMENT_METHOD_LABELS:
        method = DEFAULT_PAYMENT_METHOD
    if cycle is not None:
        enabled = cycle.enabled_payment_methods()
        if method not in enabled:
            method = enabled[0] if enabled else DEFAULT_PAYMENT_METHOD
    return method


def _parse_enabled_payment_methods_from_form(form):
    selected = []
    for key in PAYMENT_METHOD_ORDER:
        if form.get(f'pay_method_{key}') == '1':
            selected.append(key)
    return ','.join(selected) if selected else DEFAULT_PAYMENT_METHOD


def _payment_accounts_map(cycle):
    return {
        'rocket': cycle.rocket_account_number or '',
        'bkash': getattr(cycle, 'bkash_account_number', None) or '',
        'nagad': getattr(cycle, 'nagad_account_number', None) or '',
        'agrani_bank': cycle.agrani_account_number or '',
    }


def _bank_slip_abs_path(candidate):
    return _resolve_upload_path(getattr(candidate, 'bank_slip_path', None))


def _resolve_upload_path(relative_path):
    """Resolve a stored upload path only if it stays under the app upload roots."""
    from utils.safe_files import confined_existing_file
    return confined_existing_file(relative_path)


def _candidate_signature_abs_path(candidate):
    return _resolve_upload_path(getattr(candidate, 'signature_path', None))


def _user_signature_abs_path(user):
    from utils.user_signature import user_signature_abs_path
    return user_signature_abs_path(user)


def _kalpurush_font_path():
    """Prefer Kalpurush; fall back to Noto Sans Bengali for HarfBuzz shaping."""
    static_root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
    for path in (
        os.path.join(static_root, 'Fonts', 'kalpurush.ttf'),
        os.path.join(static_root, 'Fonts', 'Kalpurush.ttf'),
        os.path.join(static_root, 'fonts', 'kalpurush.ttf'),
        os.path.join(static_root, 'fonts', 'Kalpurush.ttf'),
        os.path.join(static_root, 'Fonts', 'NotoSansBengali-Regular.ttf'),
        os.path.join(static_root, 'fonts', 'NotoSansBengali-Regular.ttf'),
    ):
        if os.path.isfile(path):
            return path
    return None


def _register_admit_unicode_font():
    """Register Kalpurush (preferred) or Noto Sans Bengali for Bangla PDF text."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    static_root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
    preferred = [
        ('Kalpurush', os.path.join(static_root, 'Fonts', 'kalpurush.ttf')),
        ('Kalpurush', os.path.join(static_root, 'Fonts', 'Kalpurush.ttf')),
        ('Kalpurush', os.path.join(static_root, 'fonts', 'kalpurush.ttf')),
        ('Kalpurush', os.path.join(static_root, 'fonts', 'Kalpurush.ttf')),
        ('AdmitUnicode', os.path.join(static_root, 'Fonts', 'NotoSansBengali-Regular.ttf')),
        ('AdmitUnicode', os.path.join(static_root, 'fonts', 'NotoSansBengali-Regular.ttf')),
        ('AdmitUnicode', os.path.join(static_root, 'Fonts', 'DejaVuSans.ttf')),
        ('AdmitUnicode', os.path.join(static_root, 'fonts', 'DejaVuSans.ttf')),
    ]
    for font_name, path in preferred:
        if font_name in pdfmetrics.getRegisteredFontNames():
            return font_name
        if not os.path.isfile(path):
            continue
        try:
            pdfmetrics.registerFont(TTFont(font_name, path))
            return font_name
        except Exception:
            current_app.logger.exception('Failed to register PDF font %s', path)
    return 'Times-Roman'


def _needs_unicode_font(text):
    if not text:
        return False
    try:
        text.encode('latin-1')
        return False
    except UnicodeEncodeError:
        return True


def _contains_bengali(text):
    """True if text includes Bengali script characters."""
    if not text:
        return False
    return any('\u0980' <= ch <= '\u09FF' for ch in str(text))


class _CanvasPathAdapter:
    """Adapt reportlab.pdfgen path (close) to fontTools ReportLabPen (closePath)."""

    def __init__(self, canvas):
        self._p = canvas.beginPath()

    def moveTo(self, x, y):
        self._p.moveTo(x, y)

    def lineTo(self, x, y):
        self._p.lineTo(x, y)

    def curveTo(self, x1, y1, x2, y2, x3, y3):
        self._p.curveTo(x1, y1, x2, y2, x3, y3)

    def closePath(self):
        self._p.close()

    @property
    def path(self):
        return self._p


def _shaped_bangla_flowable(text, font_size=10, text_color=None, max_width=400):
    """HarfBuzz-shaped Bangla line as a ReportLab Flowable (fixes matra / vowel placement)."""
    from reportlab.lib.colors import black
    from reportlab.platypus import Flowable

    font_path = _kalpurush_font_path()
    if not font_path:
        return None
    try:
        import uharfbuzz as hb  # noqa: F401
    except ImportError:
        current_app.logger.warning(
            'uharfbuzz not installed — Bangla PDF will use WeasyPrint/Pango fallback'
        )
        return None

    class ShapedBanglaLine(Flowable):
        def __init__(self, raw, path, size, color, max_w):
            Flowable.__init__(self)
            self.raw = raw or ''
            self.font_path = path
            self.font_size = float(size or 10)
            self.color = color or black
            self.max_width = max_w
            self._infos = []
            self._positions = []
            self._glyph_set = None
            self._glyph_order = []
            self._upem = 1000
            self._width = 0
            self._height = max(self.font_size * 1.35, 12.0)
            self._ok = False
            try:
                self._prepare()
                self._ok = True
            except Exception:
                current_app.logger.exception('Bangla shaping failed for %r', self.raw[:40])

        def _prepare(self):
            import uharfbuzz as hb
            from fontTools.ttLib import TTFont

            ft = TTFont(self.font_path)
            self._glyph_set = ft.getGlyphSet()
            self._glyph_order = ft.getGlyphOrder()
            with open(self.font_path, 'rb') as fh:
                font_bytes = fh.read()
            blob = hb.Blob(font_bytes)
            face = hb.Face(blob)
            hbf = hb.Font(face)
            self._upem = face.upem or 1000
            buf = hb.Buffer()
            buf.add_str(self.raw)
            try:
                buf.direction = hb.Direction.LTR
                buf.script = hb.Script.from_string('Beng')
                buf.language = hb.Language.from_string('bn')
            except Exception:
                buf.guess_segment_properties()
            features = {'kern': True, 'liga': True, 'clig': True, 'calt': True, 'locl': True}
            try:
                hb.shape(hbf, buf, features)
            except TypeError:
                hb.shape(hbf, buf)
            self._infos = list(buf.glyph_infos)
            self._positions = list(buf.glyph_positions)
            scale = self.font_size / float(self._upem)
            self._width = sum(p.x_advance for p in self._positions) * scale + 2
            # Match Times paragraph leading so table LINEBELOW sits just under the name
            self._height = max(self.font_size * 1.35, 12.0)

        def wrap(self, availWidth, availHeight):
            if not self._ok:
                self.width = 0
                self.height = 0
                return 0, 0
            self.width = min(self._width, availWidth if availWidth else self._width)
            self.height = self._height
            return self.width, self.height

        def draw(self):
            if not self._ok:
                return
            from fontTools.pens.reportLabPen import ReportLabPen

            c = self.canv
            c.saveState()
            try:
                c.setFillColor(self.color)
            except Exception:
                c.setFillColor(black)
            scale = self.font_size / float(self._upem)
            # Baseline near bottom of the line box (aligns with English row text)
            c.translate(0, self.font_size * 0.18)
            xpos = 0.0
            for info, pos in zip(self._infos, self._positions):
                gid = info.codepoint
                gname = self._glyph_order[gid] if gid < len(self._glyph_order) else None
                if gname and gname in self._glyph_set:
                    c.saveState()
                    c.translate((xpos + pos.x_offset) * scale, pos.y_offset * scale)
                    c.scale(scale, scale)
                    adapter = _CanvasPathAdapter(c)
                    pen = ReportLabPen(self._glyph_set, adapter)
                    self._glyph_set[gname].draw(pen)
                    c.drawPath(adapter.path, stroke=0, fill=1)
                    c.restoreState()
                xpos += pos.x_advance
            c.restoreState()

    return ShapedBanglaLine(text, font_path, font_size, text_color, max_width)


_WEASY_BANGLA_UNAVAILABLE = False


def _bangla_weasy_image_flowable(text, font_size=10, text_color=None):
    """Render Bangla via WeasyPrint/Pango and embed as a ReportLab image.

    Sized to match ``font_size`` (never crush a full-page PNG into a tiny box).
    """
    global _WEASY_BANGLA_UNAVAILABLE
    if _WEASY_BANGLA_UNAVAILABLE:
        return None

    import html as html_lib

    font_path = _kalpurush_font_path()
    if not font_path or not text:
        return None
    try:
        from weasyprint import HTML
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Flowable
        from PIL import Image as PILImage, ImageChops
    except Exception as exc:
        _WEASY_BANGLA_UNAVAILABLE = True
        current_app.logger.warning('WeasyPrint Bangla PNG unavailable: %s', exc)
        return None

    css_color = '#000000'
    try:
        if text_color is not None and hasattr(text_color, 'hexval'):
            css_color = text_color.hexval()
    except Exception:
        css_color = '#000000'

    font_size = float(font_size or 10)
    render_pt = max(font_size, 12.0)
    resolution = 144
    # Page just large enough for the line (CSS px ≈ 96dpi); avoid A4-sized PNGs.
    page_w_px = max(320, min(900, int(len(text) * render_pt * 1.6 + 40)))
    page_h_px = int(render_pt * 2.8 + 16)
    # Base64 font — cPanel WeasyPrint often cannot fetch file:// fonts
    try:
        with open(font_path, 'rb') as fh:
            font_b64 = base64.b64encode(fh.read()).decode('ascii')
    except Exception:
        current_app.logger.exception('Bangla PNG: could not read font %s', font_path)
        return None
    snippet = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
@font-face {{
  font-family: 'AdmissionBangla';
  src: url(data:application/font-sfnt;base64,{font_b64}) format('truetype');
}}
@page {{
  margin: 0;
  size: {page_w_px}px {page_h_px}px;
}}
html, body {{
  margin: 0;
  padding: 0;
  background: #ffffff;
}}
.bn {{
  font-family: 'AdmissionBangla', sans-serif;
  font-size: {render_pt}pt;
  color: {css_color};
  line-height: 1.35;
  white-space: nowrap;
  padding: 1px 2px;
}}
</style></head>
<body><div class="bn" lang="bn">{html_lib.escape(text)}</div></body></html>"""
    try:
        png_bytes = HTML(string=snippet).write_png(resolution=resolution)
    except Exception:
        current_app.logger.exception('WeasyPrint Bangla PNG render failed')
        return None
    if not png_bytes:
        return None

    try:
        with PILImage.open(io.BytesIO(png_bytes)) as im:
            im = im.convert('RGB')
            bg = PILImage.new('RGB', im.size, (255, 255, 255))
            bbox = ImageChops.difference(im, bg).getbbox()
            if not bbox:
                return None
            l, t, r, b = bbox
            pad = 2
            im = im.crop((
                max(0, l - pad), max(0, t - pad),
                min(im.width, r + pad), min(im.height, b + pad),
            ))
            px_w, px_h = im.size
            # Reject near-full-page rasters (would be crushed to unreadably small text)
            if px_h > page_h_px * 1.5 or px_w > page_w_px * 1.5:
                current_app.logger.warning(
                    'Bangla Weasy PNG unexpectedly large (%sx%s); skipping', px_w, px_h
                )
                return None
            out = io.BytesIO()
            im.save(out, format='PNG')
            png_bytes = out.getvalue()
    except Exception:
        current_app.logger.exception('Could not crop Bangla PNG')
        return None

    bio = io.BytesIO(png_bytes)
    width_pt = px_w * 72.0 / float(resolution)
    height_pt = px_h * 72.0 / float(resolution)
    # Lock visual height to the requested point size (never crush wide names)
    target_h = max(font_size * 1.35, 12.0)
    if height_pt < 1:
        return None
    s = target_h / height_pt
    width_pt *= s
    height_pt = target_h
    min_h = target_h

    class _BanglaPng(Flowable):
        def __init__(self, reader, w, h, floor_h):
            Flowable.__init__(self)
            self._reader = reader
            self._w = w
            self._h = h
            self._floor_h = floor_h

        def wrap(self, availWidth, availHeight):
            w, h = self._w, self._h
            if availWidth and w > availWidth > 0:
                # Fit width only if height stays readable — never crush Bangla names
                s = availWidth / w
                if h * s >= self._floor_h * 0.95:
                    w = availWidth
                    h = h * s
                else:
                    w = availWidth
                    h = self._floor_h
            self.width = w
            self.height = max(h, self._floor_h)
            return self.width, self.height

        def draw(self):
            self.canv.drawImage(
                self._reader, 0, 0, width=self.width, height=self.height,
                mask='auto', preserveAspectRatio=True, anchor='sw',
            )

    return _BanglaPng(ImageReader(bio), width_pt, height_pt, min_h)


def _rl_normalize_punctuation(value):
    text = '' if value is None else str(value)
    replacements = {
        '\u2014': '-',
        '\u2013': '-',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2022': '-',
        '\u00b7': '-',
        '\u2026': '...',
        '\xa0': ' ',
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _rl_safe_text(value, fallback='-'):
    """ReportLab Times fonts are WinAnsi — strip chars that crash PDF build (e.g. em-dash)."""
    text = _rl_normalize_punctuation(value)
    if not text:
        return fallback
    return text.encode('latin-1', 'replace').decode('latin-1') or fallback


def _rl_paragraph(text, style, uni_font=None, uni_style=None):
    """Paragraph / shaped Bangla flowable for PDF table cells.

    Bengali must not use unshaped ReportLab TTFont (matras break). Prefer
    WeasyPrint/Pango PNG (cPanel), then HarfBuzz outlines (uharfbuzz).
    """
    from xml.sax.saxutils import escape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    raw = _rl_normalize_punctuation(text if text is not None else '-')
    if not raw:
        raw = '-'

    if _contains_bengali(raw):
        font_size = getattr(style, 'fontSize', 10) or 10
        color = getattr(style, 'textColor', None)
        # Prefer WeasyPrint/Pango PNG (correct Bangla shaping + size). HarfBuzz second.
        weasy = _bangla_weasy_image_flowable(raw, font_size=font_size, text_color=color)
        if weasy is not None:
            return weasy
        shaped = _shaped_bangla_flowable(raw, font_size=font_size, text_color=color)
        if shaped is not None and getattr(shaped, '_ok', False):
            return shaped
        current_app.logger.error(
            'Bangla PDF text could not be shaped (WeasyPrint and uharfbuzz both failed). '
            'Text: %r',
            raw[:60],
        )
        # Absolute last resort — matras may be wrong; prefer visible text over blank.
        if uni_font and uni_font != 'Times-Roman':
            use_style = uni_style or ParagraphStyle(
                f'{getattr(style, "name", "RL")}_UniBroken',
                parent=style,
                fontName=uni_font,
            )
            return Paragraph(escape(raw), use_style)
        return Paragraph(escape('[Bangla text — font shaping unavailable]'), style)

    if uni_font and uni_font != 'Times-Roman' and _needs_unicode_font(raw):
        use_style = uni_style or ParagraphStyle(
            f'{getattr(style, "name", "RL")}_Uni',
            parent=style,
            fontName=uni_font,
        )
        return Paragraph(escape(raw), use_style)
    return Paragraph(escape(_rl_safe_text(raw, '-')), style)


def _photo_abs_path(candidate):
    """Find candidate photo on disk; fall back to scanning the cycle upload folder."""
    path = _resolve_upload_path(candidate.photo_path)
    if path:
        return path
    from utils.safe_files import confined_existing_file
    # Fallback: scan uploads/admission_exam/cycle_<id>/ for this application_id
    try:
        cycle_id = candidate.cycle_id
        app_id = re.sub(r'[^A-Za-z0-9_-]', '_', candidate.application_id or '')
        folder_candidates = [
            os.path.join(current_app.root_path, 'static', 'uploads', 'admission_exam', f'cycle_{cycle_id}'),
            os.path.join(current_app.root_path, 'uploads', 'admission_exam', f'cycle_{cycle_id}'),
            os.path.join(os.getcwd(), 'static', 'uploads', 'admission_exam', f'cycle_{cycle_id}'),
            os.path.join(os.getcwd(), 'uploads', 'admission_exam', f'cycle_{cycle_id}'),
        ]
        for folder in folder_candidates:
            if not (app_id and os.path.isdir(folder)):
                continue
            matches = sorted(
                (f for f in os.listdir(folder)
                 if f.rsplit('.', 1)[-1].lower() in ALLOWED_PHOTO_EXTS
                 and (f.startswith(app_id) or app_id.replace('_', ' ') in f or app_id in f)),
                reverse=True,
            )
            if not matches:
                # last resort: newest image in the cycle folder
                matches = sorted(
                    (f for f in os.listdir(folder)
                     if f.rsplit('.', 1)[-1].lower() in ALLOWED_PHOTO_EXTS
                     and not f.startswith('chairman_signature')),
                    key=lambda n: os.path.getmtime(os.path.join(folder, n)),
                    reverse=True,
                )
            if matches:
                return confined_existing_file(os.path.join(folder, matches[0]))
    except Exception as e:
        current_app.logger.warning('Photo folder scan failed: %s', e)
    return None


def _signature_abs_path(cycle):
    """Resolve chairman signature; reject non-image files (e.g. accidental HTML/screenshots)."""
    path = _resolve_upload_path(getattr(cycle, 'chairman_signature_path', None))
    if not path:
        return None
    try:
        with open(path, 'rb') as f:
            head = f.read(32)
        # Skip HTML/XML mistaken uploads (showed up as tiny webpage thumbs in old stamp PDFs)
        if head.lstrip().startswith((b'<!', b'<html', b'<HTML', b'<?xml')):
            current_app.logger.warning('Ignoring non-image signature file: %s', path)
            return None
        if head[:3] == b'\xff\xd8\xff':  # JPEG
            return path
        if head[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
            return path
        # Let Pillow decide for other image types
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            im.verify()
        return path
    except Exception as e:
        current_app.logger.warning('Signature file unreadable (%s): %s', path, e)
        return None


def _pil_rgb_image(abs_path, max_size=None):
    """Open image with Pillow; return RGB PIL Image or None."""
    if not abs_path or not os.path.isfile(abs_path):
        return None
    try:
        from PIL import Image, ImageOps
        img = Image.open(abs_path)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode == 'P':
            img = img.convert('RGBA')
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        if max_size:
            resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.LANCZOS)
            img.thumbnail(max_size, resample)
        return img
    except Exception as e:
        current_app.logger.warning('Pillow could not open %s: %s', abs_path, e)
        return None


def _image_bytes_for_pdf(abs_path, max_size=(450, 540)):
    """Return JPEG bytes for admit-card image embedding (Pillow, else raw file)."""
    img = _pil_rgb_image(abs_path, max_size=max_size)
    if img is not None:
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=88)
        return buf.getvalue()
    try:
        with open(abs_path, 'rb') as f:
            return f.read()
    except Exception:
        return None


def _admit_pdf_cache_dir():
    """Writable JPEG cache; try static uploads, then instance/, then /tmp."""
    candidates = [
        os.path.join(current_app.root_path, 'static', 'uploads', 'admission_exam', '_pdf_cache'),
        os.path.join(current_app.root_path, 'uploads', 'admission_exam', '_pdf_cache'),
        os.path.join(current_app.instance_path, 'admission_exam_pdf_cache'),
        os.path.join(tempfile.gettempdir(), 'ams_admit_pdf_cache'),
    ]
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, '.write_test')
            with open(probe, 'w', encoding='utf-8') as f:
                f.write('ok')
            os.remove(probe)
            return path
        except Exception:
            continue
    raise RuntimeError('No writable admit PDF cache directory')


def _materialize_jpeg_for_reportlab(abs_path, cache_name):
    """Convert image to a plain RGB JPEG on disk; return absolute path or None.

    Course registration cards embed photos via Image('/abs/path/to.jpg') successfully
    on this host. BytesIO/ImageReader paths are unreliable with ReportLab 4.0.7 here.
    """
    if not abs_path or not os.path.isfile(abs_path):
        return None
    data = _image_bytes_for_pdf(abs_path, max_size=(600, 750))
    if not data:
        # Last resort: copy original if it is already a JPEG
        try:
            with open(abs_path, 'rb') as f:
                head = f.read(3)
                f.seek(0)
                if head == b'\xff\xd8\xff':
                    data = f.read()
        except Exception:
            data = None
    if not data:
        return None
    try:
        cache_path = os.path.join(_admit_pdf_cache_dir(), cache_name)
        with open(cache_path, 'wb') as f:
            f.write(data)
        return cache_path if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0 else None
    except Exception as e:
        current_app.logger.warning('Admit JPEG cache write failed: %s', e)
        return None


def _reportlab_flowable_image(abs_path, width, height, label='image', cache_name=None):
    """Build Platypus Image from a cached JPEG file path (cPanel / ReportLab 4 safe)."""
    from reportlab.platypus import Image as RLImage

    cache_name = cache_name or f'{label}_{os.path.basename(abs_path or "x")}.jpg'
    jpeg_path = _materialize_jpeg_for_reportlab(abs_path, cache_name)
    if not jpeg_path:
        current_app.logger.warning('Admit %s: no JPEG materialized from %r', label, abs_path)
        return None

    # Exact pattern used by course_management registration cards
    try:
        return RLImage(jpeg_path, width=width, height=height, kind='proportional')
    except Exception as e1:
        current_app.logger.warning('Admit %s Image(proportional) failed: %s', label, e1)
    try:
        return RLImage(jpeg_path, width=width, height=height)
    except Exception as e2:
        current_app.logger.warning('Admit %s Image() failed: %s', label, e2)
        return None


def _save_signature(cycle, file_storage):
    """Save chairman signature image (PNG/JPG), max 1 MB, resized. Returns (path, error)."""
    filename = secure_filename(file_storage.filename or '')
    if not filename or '.' not in filename:
        return None, 'Invalid signature file.'
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_PHOTO_EXTS:
        return None, 'Signature must be a JPG or PNG image.'

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        return None, 'Signature file is empty.'
    if size > PHOTO_MAX_UPLOAD_BYTES:
        return None, f'Signature is too large. Maximum allowed size is {PHOTO_MAX_SIZE_LABEL}.'

    try:
        from PIL import Image, ImageOps
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)
        # Keep alpha for PNG signatures (transparent background)
        if ext == 'png' and img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGBA')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.LANCZOS)
        img.thumbnail((600, 240), resample)
    except Exception:
        return None, 'Could not read the signature image. Please upload a valid JPG or PNG.'

    out_ext = 'png' if img.mode == 'RGBA' else 'jpg'
    new_name = f"chairman_signature_{int(datetime.utcnow().timestamp())}.{out_ext}"
    abs_path = os.path.join(_photo_dir(cycle), new_name)
    if out_ext == 'png':
        img.save(abs_path, format='PNG', optimize=True)
    else:
        img.save(abs_path, format='JPEG', quality=90, optimize=True)
    return os.path.join('static', 'uploads', 'admission_exam', f'cycle_{cycle.id}', new_name), None


def _parse_extra_fields(candidate):
    return parse_extra_fields(candidate)


def _collect_extra_fields(form, cycle=None, existing=None):
    return collect_extra_fields(form, cycle=cycle, existing=existing)


def _parse_dt_local(value):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M')
    except ValueError:
        return None


class _LandingHTMLSanitizer(HTMLParser):
    """Allow only basic formatting tags from the public-page rich editor."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._out = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = (tag or '').lower()
        if tag not in _LANDING_HTML_ALLOWED:
            if tag not in _LANDING_HTML_VOID:
                self._skip_depth += 1
            return
        if self._skip_depth:
            return
        safe_attrs = []
        for name, value in attrs:
            name = (name or '').lower()
            value = value or ''
            if name.startswith('on') or 'javascript:' in value.lower():
                continue
            if tag == 'a' and name == 'href':
                href = value.strip()
                if href.startswith(('http://', 'https://', 'mailto:', '/', '#')):
                    safe_attrs.append(('href', href))
                    safe_attrs.append(('target', '_blank'))
                    safe_attrs.append(('rel', 'noopener noreferrer'))
            elif name == 'style' and _LANDING_STYLE_SAFE.match(value or ''):
                safe_attrs.append(('style', value))
            elif name == 'class' and re.fullmatch(r'[a-zA-Z0-9 _\-]+', value or ''):
                safe_attrs.append(('class', value))
        attr_html = ''.join(f' {escape(n)}="{escape(v)}"' for n, v in safe_attrs)
        self._out.append(f'<{tag}{attr_html}>')

    def handle_endtag(self, tag):
        tag = (tag or '').lower()
        if tag not in _LANDING_HTML_ALLOWED:
            if tag not in _LANDING_HTML_VOID and self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag not in _LANDING_HTML_VOID:
            self._out.append(f'</{tag}>')

    def handle_data(self, data):
        if self._skip_depth:
            return
        self._out.append(str(escape(data)))

    def handle_entityref(self, name):
        if not self._skip_depth:
            self._out.append(f'&{name};')

    def handle_charref(self, name):
        if not self._skip_depth:
            self._out.append(f'&#{name};')

    def get_html(self):
        return ''.join(self._out)


def _sanitize_landing_html(raw):
    text = (raw or '').strip()
    if not text:
        return ''
    # Plain text (legacy): escape and preserve line breaks
    if '<' not in text or '>' not in text:
        return str(escape(text)).replace('\n', '<br>\n')
    parser = _LandingHTMLSanitizer()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return str(escape(text)).replace('\n', '<br>\n')
    return parser.get_html().strip()


def _landing_body_markup(body):
    """Safe Markup for templates (already sanitized on save; sanitize again on read)."""
    return Markup(_sanitize_landing_html(body))


def _parse_landing_payload(raw):
    """Parse cycle.instructions JSON into sections + attachments."""
    empty = {'sections': [], 'attachments': []}
    if not raw or not str(raw).strip():
        return empty
    text = str(raw).strip()
    try:
        data = json.loads(text)
        sections_src = None
        attachments_src = []
        if isinstance(data, dict):
            sections_src = data.get('sections')
            attachments_src = data.get('attachments') or []
            if sections_src is None and not attachments_src:
                # Unexpected shape
                sections_src = []
        elif isinstance(data, list):
            sections_src = data
        else:
            return empty

        sections = []
        for item in sections_src or []:
            if not isinstance(item, dict):
                continue
            title = (item.get('title') or '').strip()
            body = (item.get('body') or '').strip()
            if title or body:
                sections.append({'title': title or 'Information', 'body': body})

        attachments = []
        for item in attachments_src if isinstance(attachments_src, list) else []:
            if not isinstance(item, dict):
                continue
            fid = (item.get('id') or '').strip()
            name = (item.get('name') or '').strip()
            path = (item.get('path') or '').strip()
            if not fid or not name or not path:
                continue
            try:
                size = int(item.get('size') or 0)
            except (TypeError, ValueError):
                size = 0
            attachments.append({
                'id': fid,
                'name': name[:180],
                'path': path,
                'size': max(0, size),
            })
        return {'sections': sections, 'attachments': attachments}
    except (TypeError, ValueError):
        pass
    # Legacy: single plain-text instructions blob
    return {
        'sections': [{'title': 'Instructions', 'body': text}],
        'attachments': [],
    }


def _parse_landing_sections(raw):
    """Landing page sections from cycle.instructions (JSON list or legacy plain text)."""
    return _parse_landing_payload(raw)['sections']


def _parse_landing_attachments(raw):
    return _parse_landing_payload(raw)['attachments']


def _collect_landing_sections(form):
    titles = form.getlist('section_title')
    bodies = form.getlist('section_body')
    sections = []
    for i, title in enumerate(titles):
        body = bodies[i] if i < len(bodies) else ''
        title = (title or '').strip()
        body = _sanitize_landing_html(body)
        if title or body:
            sections.append({'title': title or 'Information', 'body': body})
    return sections


def _serialize_landing_payload(sections, attachments):
    payload = {
        'sections': sections or [],
        'attachments': attachments or [],
    }
    if not payload['sections'] and not payload['attachments']:
        return None
    return json.dumps(payload, ensure_ascii=False)


def _serialize_landing_sections(sections):
    """Backward-compatible helper — preserves no attachments (prefer payload helpers)."""
    return _serialize_landing_payload(sections, [])


def _landing_files_dir(cycle):
    path = os.path.join(_photo_dir(cycle), 'landing_files')
    os.makedirs(path, exist_ok=True)
    return path


def _landing_file_abs_path(rel_path):
    return _resolve_upload_path(rel_path)


def _format_file_size(num_bytes):
    try:
        n = int(num_bytes or 0)
    except (TypeError, ValueError):
        n = 0
    if n < 1024:
        return f'{n} B'
    if n < 1024 * 1024:
        return f'{n / 1024:.1f} KB'
    return f'{n / (1024 * 1024):.1f} MB'


def _write_pdf(html_content):
    """Render HTML to PDF bytes with the app's formal font setup (WeasyPrint)."""
    from weasyprint import HTML
    from utils.pdf_fonts import resolve_formal_pdf_fonts, formal_font_face_css

    formal_fonts = resolve_formal_pdf_fonts()
    if formal_fonts:
        face = f"<style>{formal_font_face_css(formal_fonts)}</style>"
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', face + '</head>', 1)
        base_url = formal_fonts['fonts_dir'].as_uri() + '/'
    else:
        base_url = request.url_root

    buffer = io.BytesIO()
    HTML(string=html_content, base_url=base_url).write_pdf(buffer)
    return buffer.getvalue()


def _ku_logo_abs_path():
    """Khulna University logo (prefer KU_logo.svg — not the Law Discipline PNG)."""
    static_root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
    for rel in (
        ('images', 'KU_logo.svg'),
        ('Images', 'KU_logo.svg'),
        ('images', 'KU_logo.png'),
        ('Images', 'KU_logo.png'),
        # Last resort only — KU_logo_2.png is the Law Discipline mark
        ('images', 'KU_logo_2.png'),
        ('Images', 'KU_logo_2.png'),
    ):
        path = os.path.join(static_root, *rel)
        if os.path.isfile(path):
            return path
    return None


def _ku_logo_for_reportlab_stamp(cache_name='ku_univ_logo_admit_v4.png'):
    """Return a raster path ReportLab can draw (SVG → PNG via WeasyPrint when needed)."""
    src = _ku_logo_abs_path()
    if not src:
        return None
    if not src.lower().endswith('.svg'):
        return src

    try:
        cache_dir = _admit_pdf_cache_dir()
        dest = os.path.join(cache_dir, cache_name)
        if os.path.isfile(dest) and os.path.getmtime(dest) >= os.path.getmtime(src):
            return dest

        from pathlib import Path
        from weasyprint import HTML

        uri = Path(src).resolve().as_uri()
        # ~37mm crest at 180 dpi for a sharp admit-card logo
        w_px = 280
        html = (
            '<!DOCTYPE html><html><head><meta charset="utf-8"/>'
            '<style>html,body{margin:0;padding:0;background:transparent;}'
            f'img{{width:{w_px}px;height:auto;display:block;}}</style></head>'
            f'<body><img src="{uri}" alt=""/></body></html>'
        )
        png_bytes = HTML(
            string=html,
            base_url=Path(src).resolve().parent.as_uri() + '/',
        ).write_png(resolution=180)
        if not png_bytes:
            return None
        with open(dest, 'wb') as fh:
            fh.write(png_bytes)
        return dest if os.path.isfile(dest) else None
    except Exception:
        current_app.logger.exception(
            'Could not rasterize KU_logo.svg for admit stamp; '
            'ensure static/images/KU_logo.svg exists on the server'
        )
        return None


# Image stamp slots — millimetres from the TOP-LEFT of the A4 page.
# Must stay in sync with admit_card_pdf.html (.slot-* rules).
ADMIT_IMAGE_SLOTS = {
    # University crest — 45% smaller than 68×68 → ~37×37
    'logo': {'left': 17, 'top': 17, 'w': 37, 'h': 37},
    # Right column beside roll/info
    'photo': {'left': 156, 'top': 82, 'w': 34, 'h': 42},
    # Above signature lines, clear of footer text
    'sig_cand': {'left': 30, 'top': 200, 'w': 48, 'h': 16},
    'sig_chair': {'left': 132, 'top': 200, 'w': 48, 'h': 16},
}

# Application-form image slots — mm from page TOP-LEFT.
# page 0 = form body (logo/photo); page 1 = declaration + signatures (never overlap body).
APP_FORM_IMAGE_SLOTS = {
    'logo': {'page': 0, 'left': 24, 'top': 13, 'w': 26, 'h': 26},
    'photo': {'page': 0, 'left': 168, 'top': 54, 'w': 26, 'h': 32},
    'sig_cand': {'page': 1, 'left': 32, 'top': 168, 'w': 55, 'h': 18},
    'sig_scrut': {'page': 1, 'left': 120, 'top': 168, 'w': 55, 'h': 18},
}


def _admit_cache_jpeg(abs_path, cache_name):
    """Materialize image as JPEG in admit cache; return absolute path or None."""
    if not abs_path or not os.path.isfile(abs_path):
        return None
    jpeg_path = _materialize_jpeg_for_reportlab(abs_path, cache_name)
    if jpeg_path and os.path.isfile(jpeg_path):
        return jpeg_path
    try:
        import shutil
        dest = os.path.join(_admit_pdf_cache_dir(), cache_name)
        shutil.copy2(abs_path, dest)
        return dest if os.path.isfile(dest) else None
    except Exception:
        current_app.logger.exception('Admit cache JPEG failed for %r', abs_path)
        return None


def _bangla_font_face_css(font_filename=None):
    """@font-face for Kalpurush / Noto — base64 so WeasyPrint needs no file:// fetch.

    On cPanel, WeasyPrint often cannot load local font files (same class of issue as
    images). Embedding the TTF as a data URI is the reliable path for Bangla shaping.
    ``font_filename`` is kept for API compatibility but is unused when the source
    font exists on disk.
    """
    path = _kalpurush_font_path()
    if not path and font_filename:
        safe_name = os.path.basename(str(font_filename))
        if re.fullmatch(r'[\w.-]+\.ttf', safe_name, flags=re.I):
            cached = os.path.join(_admit_pdf_cache_dir(), safe_name)
            if os.path.isfile(cached):
                path = cached
    if not path:
        current_app.logger.error(
            'No Bangla font for WeasyPrint (@font-face). '
            'Place kalpurush.ttf or NotoSansBengali-Regular.ttf under static/Fonts/'
        )
        return ''
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
        if not raw:
            return ''
        b64 = base64.b64encode(raw).decode('ascii')
    except Exception:
        current_app.logger.exception('Could not read Bangla font for WeasyPrint embed: %s', path)
        return ''
    # Prefer data URI; keep a relative filename as a last-resort second src.
    rel = font_filename or 'AdmitBangla.ttf'
    return f"""
@font-face {{
  font-family: 'AdmitBangla';
  src: url(data:application/font-sfnt;base64,{b64}) format('truetype'),
       url('{rel}') format('truetype');
  font-weight: normal;
  font-style: normal;
}}
"""


def _merge_pdf_overlay_bytes(base_pdf_bytes, overlay_pdf_bytes, page_index=0):
    """Stamp overlay PDF page 0 onto base PDF ``page_index`` (PyPDF2 1.26 + 3.x)."""
    out = io.BytesIO()
    try:
        from PyPDF2 import PdfReader, PdfWriter
        legacy = False
    except ImportError:
        from PyPDF2 import PdfFileReader as PdfReader
        from PyPDF2 import PdfFileWriter as PdfWriter
        legacy = True

    base = PdfReader(io.BytesIO(base_pdf_bytes))
    over = PdfReader(io.BytesIO(overlay_pdf_bytes))
    writer = PdfWriter()
    n_pages = base.getNumPages() if legacy else len(base.pages)
    page_index = max(0, min(int(page_index), n_pages - 1)) if n_pages else 0

    if legacy:
        for i in range(n_pages):
            page = base.getPage(i)
            if i == page_index:
                page.mergePage(over.getPage(0))
            writer.addPage(page)
    else:
        for i in range(n_pages):
            page = base.pages[i]
            if i == page_index:
                page.merge_page(over.pages[0])
            writer.add_page(page)
    writer.write(out)
    return out.getvalue()


def _stamp_pdf_image_slots(pdf_bytes, draws, log_label='PDF', page_index=0):
    """Stamp images onto one PDF page. ``draws``: (path, slot) with mm top-left slots."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    draws = [(p, s) for p, s in draws if p and s and os.path.isfile(p)]
    if not draws:
        return pdf_bytes

    page_h = A4[1]
    packet = io.BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=A4)
    for path, slot in draws:
        x = float(slot['left']) * mm
        w = float(slot['w']) * mm
        h = float(slot['h']) * mm
        y = page_h - (float(slot['top']) + float(slot['h'])) * mm
        try:
            c.drawImage(
                path, x, y, width=w, height=h,
                preserveAspectRatio=True, mask='auto',
            )
        except Exception:
            current_app.logger.exception('%s stamp drawImage failed for %r', log_label, path)
    c.save()
    try:
        return _merge_pdf_overlay_bytes(pdf_bytes, packet.getvalue(), page_index=page_index)
    except Exception:
        current_app.logger.exception('%s image overlay merge failed; returning text-only PDF', log_label)
        return pdf_bytes


def _stamp_admit_card_images(
    pdf_bytes,
    *,
    logo_path=None,
    photo_path=None,
    candidate_sig_path=None,
    chairman_sig_path=None,
    show_photo=True,
):
    """Draw logo/photo/signatures into ADMIT_IMAGE_SLOTS."""
    draws = [
        (logo_path, ADMIT_IMAGE_SLOTS['logo']),
        (candidate_sig_path, ADMIT_IMAGE_SLOTS['sig_cand']),
        (chairman_sig_path, ADMIT_IMAGE_SLOTS['sig_chair']),
    ]
    if show_photo:
        draws.insert(1, (photo_path, ADMIT_IMAGE_SLOTS['photo']))
    return _stamp_pdf_image_slots(pdf_bytes, draws, log_label='Admit', page_index=0)


def _stamp_application_form_images(
    pdf_bytes,
    *,
    logo_path=None,
    photo_path=None,
    candidate_sig_path=None,
    scrutinizer_sig_path=None,
    show_photo=True,
):
    """Stamp logo/photo on page 0; signatures on declaration page (usually page 1)."""
    by_page = {}
    pairs = [
        (logo_path, APP_FORM_IMAGE_SLOTS['logo']),
        (candidate_sig_path, APP_FORM_IMAGE_SLOTS['sig_cand']),
        (scrutinizer_sig_path, APP_FORM_IMAGE_SLOTS['sig_scrut']),
    ]
    if show_photo:
        pairs.insert(1, (photo_path, APP_FORM_IMAGE_SLOTS['photo']))
    for path, slot in pairs:
        if not path or not slot:
            continue
        pg = int(slot.get('page', 0))
        by_page.setdefault(pg, []).append((path, slot))
    for pg, draws in sorted(by_page.items()):
        pdf_bytes = _stamp_pdf_image_slots(
            pdf_bytes, draws, log_label='AppForm', page_index=pg,
        )
    return pdf_bytes


def _render_admit_card_pdf(candidate):
    """Admit card: WeasyPrint text/Bangla + ReportLab-stamped images (cPanel-safe)."""
    try:
        pdf_bytes = _render_admit_card_pdf_weasy(candidate)
        if pdf_bytes and len(pdf_bytes) > 2000:
            current_app.logger.info(
                'Admit card WEASY+STAMP for %s bytes=%s',
                candidate.application_id, len(pdf_bytes),
            )
            return pdf_bytes
        current_app.logger.warning(
            'Admit card WeasyPrint produced empty/short PDF for %s; using ReportLab',
            candidate.application_id,
        )
    except Exception:
        current_app.logger.exception(
            'Admit card WeasyPrint failed for %s; using ReportLab fallback',
            candidate.application_id,
        )
    return _render_admit_card_pdf_reportlab(candidate)


def _render_admit_card_pdf_weasy(candidate):
    """WeasyPrint layout (Bangla OK) then stamp logo/photo/signatures with ReportLab."""
    import shutil
    from pathlib import Path
    from weasyprint import HTML

    cycle = candidate.cycle
    extra = _parse_extra_fields(candidate)
    admit_fields = fields_where(cycle, 'on_admit')
    show_photo = any(f.get('key') == 'photo' for f in admit_fields)
    show_roll_box = any(f.get('key') == 'roll_no' for f in admit_fields)
    photo_src = _photo_abs_path(candidate) if show_photo else None
    chairman_sig_src = _signature_abs_path(cycle) if cycle else None
    candidate_sig_src = _candidate_signature_abs_path(candidate)
    logo_src = _ku_logo_abs_path()

    cache_dir = _admit_pdf_cache_dir()
    cid = candidate.id

    logo_path = _ku_logo_for_reportlab_stamp(f'admit_{cid}_ku_logo_v4.png')
    if not logo_path:
        # Non-SVG fallback already returned by _ku_logo_for_reportlab_stamp; try raw path
        logo_path = logo_src if (logo_src and not logo_src.lower().endswith('.svg')
                                 and os.path.isfile(logo_src)) else None
    photo_path = _admit_cache_jpeg(photo_src, f'admit_{cid}_photo.jpg') if show_photo else None
    cand_sig_path = _admit_cache_jpeg(candidate_sig_src, f'admit_{cid}_cand_sig.jpg')
    chair_sig_path = _admit_cache_jpeg(chairman_sig_src, f'admit_{cid}_chair_sig.jpg')

    bangla_font_file = None
    font_path = _kalpurush_font_path()
    if font_path:
        bangla_font_file = 'AdmitBangla.ttf'
        dest_font = os.path.join(cache_dir, bangla_font_file)
        try:
            if (not os.path.isfile(dest_font)
                    or os.path.getmtime(font_path) > os.path.getmtime(dest_font)):
                shutil.copy2(font_path, dest_font)
        except Exception:
            current_app.logger.exception('Could not copy Bangla font into admit cache')
            bangla_font_file = None

    info_rows = []
    for field in admit_fields:
        if field.get('key') in ('photo', 'roll_no', 'candidate_signature'):
            continue
        label = field.get('label') or field['key']
        if field.get('key') == 'full_name':
            label = 'Name of Candidate (English)'
        elif field.get('key') == 'name_bangla':
            label = 'Name of Candidate (Bangla)'
        val = candidate_field_value(candidate, field, extra) or '—'
        info_rows.append({
            'label': label,
            'value': val,
            'is_bangla': _contains_bengali(val) or field.get('key') == 'name_bangla',
        })
    if not info_rows:
        info_rows = [{
            'label': 'Name of Candidate',
            'value': candidate.full_name or '—',
            'is_bangla': _contains_bengali(candidate.full_name),
        }]

    bangla_font_face = _bangla_font_face_css(bangla_font_file)
    if not bangla_font_face:
        raise RuntimeError('Bangla @font-face unavailable for admit-card WeasyPrint PDF')

    current_app.logger.info(
        'Admit Weasy+stamp cand=%s logo=%s photo=%s cand_sig=%s chair_sig=%s bangla_font=%s',
        candidate.application_id,
        bool(logo_path), bool(photo_path), bool(cand_sig_path), bool(chair_sig_path),
        bool(font_path),
    )

    html_content = render_template(
        'admission_exam/admit_card_pdf.html',
        candidate=candidate,
        cycle=cycle,
        info_rows=info_rows,
        show_photo=show_photo,
        show_roll_box=show_roll_box,
        slots=ADMIT_IMAGE_SLOTS,
        bangla_font_face=bangla_font_face,
    )

    base_url = Path(cache_dir).resolve().as_uri()
    if not base_url.endswith('/'):
        base_url += '/'

    buffer = io.BytesIO()
    HTML(string=html_content, base_url=base_url).write_pdf(buffer)
    pdf_bytes = buffer.getvalue()

    return _stamp_admit_card_images(
        pdf_bytes,
        logo_path=logo_path,
        photo_path=photo_path,
        candidate_sig_path=cand_sig_path,
        chairman_sig_path=chair_sig_path,
        show_photo=show_photo,
    )


def _render_admit_card_pdf_reportlab(candidate):
    """ReportLab fallback admit card (logo + photos via on-disk JPEG cache)."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    cycle = candidate.cycle
    extra = _parse_extra_fields(candidate)
    admit_fields = fields_where(cycle, 'on_admit')
    show_photo = any(f.get('key') == 'photo' for f in admit_fields)
    show_roll_box = any(f.get('key') == 'roll_no' for f in admit_fields)
    photo_src = _photo_abs_path(candidate) if show_photo else None
    chairman_sig_src = _signature_abs_path(cycle) if cycle else None
    candidate_sig_src = _candidate_signature_abs_path(candidate)
    uni_font = _register_admit_unicode_font()

    if show_photo and not photo_src:
        current_app.logger.warning(
            'Admit card: photo missing for %s (db_path=%r, root=%s)',
            candidate.application_id, candidate.photo_path, current_app.root_path,
        )

    def _p(text, style):
        return _rl_paragraph(text, style, uni_font=uni_font)

    buffer = io.BytesIO()
    # Keep content inside the decorative border (drawn at 12mm from page edge)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    navy = colors.HexColor('#1a3a6b')
    content_w = 174 * mm
    style_uni = ParagraphStyle(
        'AdmitUni', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=18, alignment=TA_CENTER, textColor=colors.black, spaceAfter=3, leading=22,
    )
    style_disc = ParagraphStyle(
        'AdmitDisc', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=13, alignment=TA_CENTER, textColor=colors.black, spaceAfter=2, leading=16,
    )
    style_cycle = ParagraphStyle(
        'AdmitCycle', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=12, alignment=TA_CENTER, textColor=colors.HexColor('#333333'),
        spaceAfter=4, leading=15,
    )
    style_title = ParagraphStyle(
        'AdmitTitle', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=14, alignment=TA_CENTER, textColor=navy, spaceBefore=2, spaceAfter=2,
    )
    style_label = ParagraphStyle(
        'AdmitLabel', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=11, alignment=TA_LEFT, textColor=colors.HexColor('#333333'), leading=14,
    )
    style_value = ParagraphStyle(
        'AdmitValue', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=12, alignment=TA_LEFT, textColor=colors.black, leading=15,
    )
    style_small = ParagraphStyle(
        'AdmitSmall', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=10, alignment=TA_LEFT, textColor=colors.HexColor('#333333'), leading=14,
    )
    style_footer = ParagraphStyle(
        'AdmitFooter', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=8.5, alignment=TA_CENTER, textColor=colors.HexColor('#555555'),
        leading=12,
    )
    style_print_note = ParagraphStyle(
        'AdmitPrintNote', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor('#cc0000'),
        leading=13,
    )
    style_sign = ParagraphStyle(
        'AdmitSign', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=9, alignment=TA_CENTER, textColor=colors.black, spaceBefore=3,
    )
    # Photo — materialize JPEG under static/_pdf_cache, then Image(path)
    photo_w, photo_h = 34 * mm, 42 * mm
    photo_cell = None
    photo_img = None
    if show_photo:
        photo_img = _reportlab_flowable_image(
            photo_src, photo_w, photo_h,
            label='photo',
            cache_name=f'candidate_{candidate.id}_photo.jpg',
        )
        if photo_img is not None:
            photo_cell = Table([[photo_img]], colWidths=[photo_w], rowHeights=[photo_h])
            photo_cell.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#444444')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
        else:
            miss = Paragraph(
                escape('PHOTO MISSING' if not photo_src else 'PHOTO ERROR'),
                ParagraphStyle(
                    'AdmitPhotoMiss', parent=styles['Normal'], fontName='Times-Bold',
                    fontSize=9, alignment=TA_CENTER, textColor=colors.HexColor('#b00020'),
                ),
            )
            photo_cell = Table([[miss]], colWidths=[photo_w], rowHeights=[photo_h])
            photo_cell.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#444444')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))

    info_rows = []
    for field in admit_fields:
        if field.get('key') in ('photo', 'roll_no', 'candidate_signature'):
            continue  # photo box / roll box / signature images handled separately
        label = field.get('label') or field['key']
        if field.get('key') == 'full_name':
            label = 'Name of Candidate (English)'
        elif field.get('key') == 'name_bangla':
            label = 'Name of Candidate (Bangla)'
        val = candidate_field_value(candidate, field, extra)
        info_rows.append([_p(label, style_label), _p(val or '-', style_value)])
    if not info_rows:
        info_rows = [[_p('Name of Candidate', style_label), _p(candidate.full_name, style_value)]]

    info_width = 80 * mm if show_photo else content_w - 50 * mm
    label_width = 50 * mm
    info_table = Table(info_rows, colWidths=[label_width, info_width])
    info_table.setStyle(TableStyle([
        # BOTTOM keeps Bangla PNG/shaped glyphs on the same baseline as English rows
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, -2), 0.35, colors.HexColor('#bbbbbb')),
    ]))

    # Two-row roll box — extra space between label and value (no INNERGRID line)
    style_roll_lbl = ParagraphStyle(
        'AdmitRollLbl', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#444444'),
    )
    style_roll_val = ParagraphStyle(
        'AdmitRollVal', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=22, leading=26, alignment=TA_CENTER, textColor=navy,
        spaceBefore=4,
    )
    roll_table = None
    left_col_w = 132 * mm if show_photo else content_w
    if show_roll_box:
        roll_table = Table(
            [
                [Paragraph('ROLL NUMBER', style_roll_lbl)],
                [Paragraph(escape(_rl_safe_text(candidate.roll_no or '-')), style_roll_val)],
            ],
            colWidths=[left_col_w],
        )
        roll_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eef3fb')),
            ('BOX', (0, 0), (-1, -1), 1.2, navy),
            ('TOPPADDING', (0, 0), (0, 0), 7),
            ('BOTTOMPADDING', (0, 0), (0, 0), 2),
            ('TOPPADDING', (0, 1), (0, 1), 8),
            ('BOTTOMPADDING', (0, 1), (0, 1), 9),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

    # NOTE: Do NOT wrap nested tables in KeepTogether — ReportLab 4.0.7 LayoutError.
    left_bits = []
    if roll_table is not None:
        left_bits.extend([[roll_table], [Spacer(1, 6 * mm)]])
    left_bits.append([info_table])
    left_col = Table(left_bits, colWidths=[left_col_w])
    left_col.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    if show_photo and photo_cell is not None:
        main_table = Table([[left_col, photo_cell]], colWidths=[left_col_w + 2 * mm, photo_w + 4 * mm])
        main_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (1, 0), (1, 0), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        main_table = left_col

    exam_bits = []
    if cycle and cycle.exam_date:
        exam_bits.append(
            f'<b>Date &amp; Time of Examination:</b> {escape(_rl_safe_text(cycle.exam_date))}'
        )
    if cycle and cycle.exam_venue:
        exam_bits.append(f'<b>Venue:</b> {escape(_rl_safe_text(cycle.exam_venue))}')
    exam_block = None
    if exam_bits:
        exam_block = Table(
            [[Paragraph('<br/>'.join(exam_bits), style_small)]],
            colWidths=[content_w],
        )
        exam_block.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#999999')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
            ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

    def _sign_column(label, image_path=None, cache_name=None):
        flow = []
        sig_img = None
        if image_path:
            sig_img = _reportlab_flowable_image(
                image_path, 48 * mm, 18 * mm,
                label='signature',
                cache_name=cache_name or f'cycle_{cycle.id if cycle else 0}_signature.jpg',
            )
        if sig_img is not None:
            flow.append(sig_img)
        else:
            flow.append(Spacer(1, 18 * mm))
        flow.append(Paragraph(escape(_rl_safe_text(label)), style_sign))
        rows = [[f] for f in flow]
        inner = Table(rows, colWidths=[78 * mm])
        inner.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LINEABOVE', (0, -1), (-1, -1), 0.7, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return inner

    sig_table = Table(
        [[
            _sign_column(
                'Signature of Candidate',
                candidate_sig_src,
                cache_name=f'candidate_{candidate.id}_signature.jpg',
            ),
            _sign_column(
                'Chairman, Admission Committee',
                chairman_sig_src,
                cache_name=f'cycle_{cycle.id if cycle else 0}_signature.jpg',
            ),
        ]],
        colWidths=[content_w / 2, content_w / 2],
    )
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    title_box = Table(
        [[Paragraph('ADMIT CARD', style_title)]],
        colWidths=[60 * mm],
    )
    title_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.2, navy),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eef3fb')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    title_wrap = Table([[title_box]], colWidths=[content_w])
    title_wrap.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    logo_raster = _ku_logo_for_reportlab_stamp('ku_univ_logo_admit_v4.png')
    logo_img = _reportlab_flowable_image(
        logo_raster, 37 * mm, 37 * mm,
        label='ku_logo',
        cache_name='ku_univ_logo_admit_rl_v4.jpg',
    ) if logo_raster else None
    if logo_img is None:
        logo_cell = Spacer(1, 37 * mm)
    else:
        logo_cell = logo_img
    header_text = Table(
        [
            [Paragraph(escape(current_tenant().university_name), style_uni)],
            [Paragraph(escape(current_tenant().name), style_disc)],
            [Paragraph(escape(_rl_safe_text(cycle.name if cycle else 'Admission Exam')), style_cycle)],
        ],
        colWidths=[content_w - 82 * mm],
    )
    header_text.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    header_block = Table(
        [[logo_cell, header_text, Spacer(1, 37 * mm)]],
        colWidths=[41 * mm, content_w - 82 * mm, 41 * mm],
    )
    header_block.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    footer_note = Paragraph(
        escape(_rl_safe_text(
            'This admit card must be presented at the examination hall along with a valid photo ID. '
            f'Issued electronically by the Admission Committee, {current_tenant().display_with_university}.'
        )),
        style_footer,
    )
    print_note = Paragraph(
        escape(
            'Important: Please bring a COLOUR PRINT of this admit card to the examination hall.'
        ),
        style_print_note,
    )

    # Full-page vertical rhythm: distribute leftover space so the card fills A4 evenly.
    usable_h = A4[1] - doc.topMargin - doc.bottomMargin
    # Approximate fixed block heights (generous; leftover becomes breathing room)
    approx_fixed = (
        28 * mm   # header
        + 16 * mm  # title
        + 58 * mm  # roll + info + photo
        + (22 * mm if exam_block else 0)
        + 40 * mm  # signatures
        + 22 * mm  # footer + red note
    )
    leftover = max(usable_h - approx_fixed, 24 * mm)
    # Weight gaps: after title, after info, after exam, before footer
    g1 = leftover * 0.18  # header → title breathing
    g2 = leftover * 0.22  # title → main
    g3 = leftover * 0.18  # main → exam
    g4 = leftover * 0.28  # exam → signatures (push signs lower)
    g5 = leftover * 0.14  # signatures → notes

    page_rows = [
        [header_block],
        [Spacer(1, g1)],
        [title_wrap],
        [Spacer(1, g2)],
        [main_table],
        [Spacer(1, g3)],
    ]
    if exam_block:
        page_rows.append([exam_block])
        page_rows.append([Spacer(1, g4)])
    else:
        page_rows.append([Spacer(1, g3 + g4)])
    page_rows.extend([
        [sig_table],
        [Spacer(1, g5)],
        [footer_note],
        [Spacer(1, 4 * mm)],
        [print_note],
    ])

    page_table = Table(page_rows, colWidths=[content_w])
    page_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    body = [page_table]

    def _draw_border(canvas_obj, _doc):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(navy)
        canvas_obj.setLineWidth(2)
        canvas_obj.roundRect(
            12 * mm, 12 * mm,
            A4[0] - 24 * mm, A4[1] - 24 * mm,
            4, stroke=1, fill=0,
        )
        canvas_obj.restoreState()

    doc.build(body, onFirstPage=_draw_border, onLaterPages=_draw_border)
    pdf_bytes = buffer.getvalue()
    current_app.logger.info(
        'Admit card REPORTLAB for %s photo_src=%r photo_ok=%s chairman_sig=%s candidate_sig=%s bytes=%s',
        candidate.application_id, photo_src,
        photo_img is not None, bool(chairman_sig_src), bool(candidate_sig_src), len(pdf_bytes),
    )
    return pdf_bytes


def _render_application_form_pdf(candidate):
    """Application form: WeasyPrint text/Bangla + ReportLab-stamped images (admit-card style).

    Returns ``(pdf_bytes, engine_tag)`` so downloads can show which path ran.
    """
    try:
        # Fail fast if the Weasy template was not uploaded to cPanel
        from flask import current_app as _ca
        try:
            _ca.jinja_env.get_template('admission_exam/application_form_pdf.html')
        except Exception as te:
            raise RuntimeError(
                'Missing template admission_exam/application_form_pdf.html — '
                'upload blueprints/admission_exam/templates/admission_exam/application_form_pdf.html'
            ) from te

        pdf_bytes = _render_application_form_pdf_weasy(candidate)
        if pdf_bytes and len(pdf_bytes) > 2000:
            current_app.logger.info(
                'Application form %s for %s bytes=%s',
                APP_FORM_PDF_ENGINE, candidate.application_id, len(pdf_bytes),
            )
            return pdf_bytes, APP_FORM_PDF_ENGINE
        current_app.logger.warning(
            'Application form WeasyPrint produced empty/short PDF for %s; using ReportLab',
            candidate.application_id,
        )
    except Exception:
        current_app.logger.exception(
            'Application form WeasyPrint failed for %s; using ReportLab fallback',
            candidate.application_id,
        )
    return _render_application_form_pdf_reportlab(candidate), 'APP-RL-FALLBACK'


def _application_form_section_data(candidate):
    """Shared field/section payload for Weasy + ReportLab application form PDFs."""
    cycle = candidate.cycle
    extra = _parse_extra_fields(candidate)
    pdf_fields = fields_where(cycle, 'on_app_pdf')
    show_photo = any(f.get('key') == 'photo' for f in pdf_fields)
    pay_method = (getattr(candidate, 'payment_method', None) or DEFAULT_PAYMENT_METHOD).strip().lower()
    mfs_labels = mfs_field_labels(pay_method)

    identity_rows = []
    for field in pdf_fields:
        if field.get('section') != 'identity' or field.get('key') == 'photo':
            continue
        val = candidate_field_value(candidate, field, extra) or '—'
        identity_rows.append({
            'label': field.get('label') or field['key'],
            'value': val,
            'is_bangla': _contains_bengali(val),
        })
    identity_rows.append({
        'label': 'Applied At',
        'value': format_bd(candidate.created_at, '%d %B %Y, %I:%M %p', default='—'),
        'is_bangla': False,
    })

    section_order = [
        ('personal', 'Personal Information'),
        ('academic', 'Academic Information'),
        ('payment', 'Payment & Status'),
        ('other', 'Other Information'),
    ]
    section_rows = {key: [] for key, _ in section_order}
    for field in pdf_fields:
        key = field.get('key')
        if key in ('photo', 'candidate_signature') or field.get('section') == 'identity':
            continue
        if key in ACADEMIC_FIELD_KEYS:
            continue
        if key == 'bank_slip':
            continue
        if is_mfs_payment_method(pay_method) and key in ('bank_slip_txn_no', 'bank_slip'):
            continue
        if pay_method == 'agrani_bank' and key in ('rocket_txn_id', 'rocket_sender_phone'):
            continue
        sec = field.get('section') or 'personal'
        if sec not in section_rows:
            sec = 'other'
        val = candidate_field_value(candidate, field, extra)
        label = field.get('label') or key
        if is_mfs_payment_method(pay_method):
            if key == 'rocket_txn_id':
                label = mfs_labels['txn']
            elif key == 'rocket_sender_phone':
                label = mfs_labels['sender']
        display = val or '—'
        section_rows[sec].append({
            'label': label,
            'value': display,
            'is_bangla': key == 'name_bangla' or _contains_bengali(display),
        })
    section_rows['payment'].append({
        'label': 'Application Status',
        'value': candidate.application_status or '—',
        'is_bangla': False,
    })
    if candidate.payment_note:
        section_rows['payment'].append({
            'label': 'Payment Note',
            'value': candidate.payment_note,
            'is_bangla': _contains_bengali(candidate.payment_note),
        })

    academic_rows = academic_display_rows(extra) if academic_form_enabled(cycle) else []
    academic_cols = [col_label for _suffix, col_label in ACADEMIC_COL_SUFFIXES]

    sections = []
    sec_num = 1
    for sec_key, sec_title in section_order:
        if sec_key == 'academic' and academic_rows:
            sections.append({
                'number': sec_num,
                'title': sec_title,
                'kind': 'academic',
                'rows': [],
            })
            sec_num += 1
            continue
        rows = section_rows.get(sec_key) or []
        if not rows:
            continue
        sections.append({
            'number': sec_num,
            'title': sec_title,
            'kind': 'kv',
            'rows': rows,
        })
        sec_num += 1

    decl_text = get_declaration_text(cycle)
    declaration_paras = [p.strip() for p in re.split(r'\n+', decl_text) if p.strip()]

    verifier = getattr(candidate, 'verifier', None)
    if verifier is None and candidate.verified_by:
        verifier = User.query.get(candidate.verified_by)
    verifier_name = (
        verifier.full_name if verifier and getattr(verifier, 'full_name', None) else None
    )

    return {
        'cycle': cycle,
        'extra': extra,
        'pdf_fields': pdf_fields,
        'show_photo': show_photo,
        'identity_rows': identity_rows,
        'sections': sections,
        'academic_rows': academic_rows,
        'academic_cols': academic_cols,
        'declaration_number': sec_num,
        'declaration_paras': declaration_paras,
        'verifier': verifier,
        'verifier_name': verifier_name,
        'photo_src': _photo_abs_path(candidate) if show_photo else None,
        'candidate_sig_src': _candidate_signature_abs_path(candidate),
        'scrutinizer_sig_src': _user_signature_abs_path(verifier),
    }


def _render_application_form_pdf_weasy(candidate):
    """WeasyPrint layout (Bangla OK) then stamp logo/photo/signatures with ReportLab."""
    import shutil
    from pathlib import Path
    from weasyprint import HTML

    ctx = _application_form_section_data(candidate)
    cache_dir = _admit_pdf_cache_dir()
    cid = candidate.id

    logo_src = _ku_logo_abs_path()
    logo_path = _ku_logo_for_reportlab_stamp(f'appform_{cid}_ku_logo.png')
    if not logo_path:
        logo_path = logo_src if (
            logo_src and not logo_src.lower().endswith('.svg') and os.path.isfile(logo_src)
        ) else None
    photo_path = (
        _admit_cache_jpeg(ctx['photo_src'], f'appform_{cid}_photo.jpg')
        if ctx['show_photo'] else None
    )
    cand_sig_path = _admit_cache_jpeg(ctx['candidate_sig_src'], f'appform_{cid}_cand_sig.jpg')
    scrut_sig_path = _admit_cache_jpeg(ctx['scrutinizer_sig_src'], f'appform_{cid}_scrut_sig.jpg')

    bangla_font_file = None
    font_path = _kalpurush_font_path()
    if font_path:
        bangla_font_file = 'AdmitBangla.ttf'
        dest_font = os.path.join(cache_dir, bangla_font_file)
        try:
            if (not os.path.isfile(dest_font)
                    or os.path.getmtime(font_path) > os.path.getmtime(dest_font)):
                shutil.copy2(font_path, dest_font)
        except Exception:
            current_app.logger.exception('Could not copy Bangla font into app-form cache')
            bangla_font_file = None

    bangla_font_face = _bangla_font_face_css(bangla_font_file)
    if not bangla_font_face:
        raise RuntimeError(
            'Bangla @font-face unavailable for application form WeasyPrint PDF'
        )

    current_app.logger.info(
        'AppForm Weasy+stamp cand=%s logo=%s photo=%s cand_sig=%s scrut_sig=%s bangla_font=%s',
        candidate.application_id,
        bool(logo_path), bool(photo_path), bool(cand_sig_path), bool(scrut_sig_path),
        bool(font_path),
    )

    html_content = render_template(
        'admission_exam/application_form_pdf.html',
        candidate=candidate,
        cycle=ctx['cycle'],
        identity_rows=ctx['identity_rows'],
        sections=ctx['sections'],
        academic_rows=ctx['academic_rows'],
        academic_cols=ctx['academic_cols'],
        declaration_number=ctx['declaration_number'],
        declaration_paras=ctx['declaration_paras'],
        verifier_name=ctx['verifier_name'],
        show_photo=ctx['show_photo'],
        slots=APP_FORM_IMAGE_SLOTS,
        bangla_font_face=bangla_font_face,
    )

    base_url = Path(cache_dir).resolve().as_uri()
    if not base_url.endswith('/'):
        base_url += '/'

    buffer = io.BytesIO()
    HTML(string=html_content, base_url=base_url).write_pdf(buffer)
    pdf_bytes = buffer.getvalue()

    return _stamp_application_form_images(
        pdf_bytes,
        logo_path=logo_path,
        photo_path=photo_path,
        candidate_sig_path=cand_sig_path,
        scrutinizer_sig_path=scrut_sig_path,
        show_photo=ctx['show_photo'],
    )


def _render_application_form_pdf_reportlab(candidate):
    """ReportLab fallback application form PDF."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ctx = _application_form_section_data(candidate)
    cycle = ctx['cycle']
    show_photo = ctx['show_photo']
    photo_src = ctx['photo_src']
    candidate_sig_src = ctx['candidate_sig_src']
    scrutinizer_sig_src = ctx['scrutinizer_sig_src']
    verifier = ctx['verifier']
    uni_font = _register_admit_unicode_font()

    def _p(text, style):
        return _rl_paragraph(text, style, uni_font=uni_font)

    # Compact one-page layout: tight margins inside the navy border (12 mm inset).
    content_w = 182 * mm
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=11 * mm,
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor('#1a3a6b')
    style_uni = ParagraphStyle(
        'AppUni', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=13, leading=15, alignment=TA_CENTER, spaceAfter=0, spaceBefore=0,
    )
    style_sub = ParagraphStyle(
        'AppSub', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=9.5, leading=11, alignment=TA_CENTER,
        textColor=colors.HexColor('#333333'), spaceAfter=0, spaceBefore=1,
    )
    style_title = ParagraphStyle(
        'AppTitle', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=10.5, leading=12, alignment=TA_CENTER, textColor=navy,
    )
    style_label = ParagraphStyle(
        'AppLabel', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=8, leading=10, alignment=TA_LEFT, textColor=colors.HexColor('#333333'),
    )
    style_value = ParagraphStyle(
        'AppValue', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=8.5, leading=10.5, alignment=TA_LEFT,
    )
    # Bangla via Weasy PNG — keep clearly larger than English 8.5pt labels
    style_value_bn = ParagraphStyle(
        'AppValueBn', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=13, leading=16, alignment=TA_LEFT,
    )
    style_sec = ParagraphStyle(
        'AppSec', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=9, leading=11, alignment=TA_LEFT, textColor=navy,
        spaceBefore=3, spaceAfter=2,
    )
    style_foot = ParagraphStyle(
        'AppFoot', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=7, leading=9, alignment=TA_CENTER,
        textColor=colors.HexColor('#555555'), spaceBefore=3, spaceAfter=0,
    )
    style_decl = ParagraphStyle(
        'AppDecl', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=7.5, leading=9.5, alignment=TA_JUSTIFY, spaceBefore=1, spaceAfter=1,
    )
    style_sign = ParagraphStyle(
        'AppSign', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=7.5, leading=9, alignment=TA_CENTER, textColor=colors.black, spaceBefore=1,
    )
    style_th = ParagraphStyle(
        'AppTh', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=6.5, alignment=TA_CENTER, leading=8,
    )
    style_td = ParagraphStyle(
        'AppTd', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=6.5, alignment=TA_CENTER, leading=8,
    )

    photo_w, photo_h = 24 * mm, 30 * mm
    photo_cell = None
    if show_photo:
        photo_img = _reportlab_flowable_image(
            photo_src, photo_w, photo_h,
            label='app_photo',
            cache_name=f'form_{candidate.id}_photo.jpg',
        )
        if photo_img is not None:
            photo_cell = Table([[photo_img]], colWidths=[photo_w], rowHeights=[photo_h])
            photo_cell.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor('#444444')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
        else:
            photo_cell = Table([[_p('No photo', style_value)]], colWidths=[photo_w], rowHeights=[photo_h])
            photo_cell.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor('#444444')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))

    title_box = Table([[Paragraph('APPLICATION FORM', style_title)]], colWidths=[48 * mm])
    title_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.0, navy),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eef3fb')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    title_wrap = Table([[title_box]], colWidths=[content_w])
    title_wrap.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    id_rows = []
    for row in ctx['identity_rows']:
        val_style = style_value_bn if row.get('is_bangla') else style_value
        id_rows.append([_p(row['label'], style_label), _p(row['value'], val_style)])
    id_table = Table(id_rows, colWidths=[38 * mm, (content_w - 68 * mm) if photo_cell else (content_w - 38 * mm)])
    id_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
    ]))
    if photo_cell is not None:
        head_row = Table([[id_table, photo_cell]], colWidths=[content_w - 30 * mm, 30 * mm])
        head_row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (1, 0), (1, 0), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        head_row = id_table

    def _section_table(rows):
        t = Table(rows, colWidths=[46 * mm, content_w - 46 * mm])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('TOPPADDING', (0, 0), (-1, -1), 1.8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('LINEBELOW', (0, 0), (-1, -2), 0.3, colors.HexColor('#bbbbbb')),
        ]))
        return t

    academic_table = None
    if ctx['academic_rows']:
        header = [_p('Name of the Examination', style_th)]
        for col_label in ctx['academic_cols']:
            header.append(_p(col_label, style_th))
        acad_rows = [header]
        for arow in ctx['academic_rows']:
            acad_rows.append([
                _p(arow['label'], style_td),
                _p(arow['year'] or '-', style_td),
                _p(arow['board'] or '-', style_td),
                _p(arow['institution'] or '-', style_td),
                _p(arow['cgpa'] or '-', style_td),
                _p(arow['percentage'] or '-', style_td),
            ])
        first_col = 32 * mm
        other_w = (content_w - first_col) / max(len(ctx['academic_cols']), 1)
        col_w = [first_col] + [other_w] * len(ctx['academic_cols'])
        academic_table = Table(acad_rows, colWidths=col_w)
        academic_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#666666')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef3fb')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 1.5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1.5),
        ]))

    def _app_sign_column(label, image_path=None, cache_name=None, sublabel=None, col_w=None):
        col_w = col_w or 80 * mm
        flow = []
        sig_img = None
        if image_path:
            sig_img = _reportlab_flowable_image(
                image_path, 36 * mm, 10 * mm,
                label='app_signature',
                cache_name=cache_name or 'app_signature.jpg',
            )
        if sig_img is not None:
            flow.append(sig_img)
        else:
            flow.append(Spacer(1, 10 * mm))
        flow.append(Paragraph(escape(_rl_safe_text(label)), style_sign))
        if sublabel:
            flow.append(_p(sublabel, style_sign))
        rows = [[f] for f in flow]
        inner = Table(rows, colWidths=[col_w])
        inner.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LINEABOVE', (0, -1 if not sublabel else -2), (-1, -1 if not sublabel else -2),
             0.6, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 0.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
        ]))
        return inner

    # Match Weasy slots: logo +20% (26mm), nudged ~10% right
    logo_mm = 26 * mm
    logo_raster = _ku_logo_for_reportlab_stamp('ku_univ_logo_app_form_v3.png')
    logo_img = _reportlab_flowable_image(
        logo_raster, logo_mm, logo_mm,
        label='ku_logo_app',
        cache_name='ku_univ_logo_app_form_rl_v3.jpg',
    ) if logo_raster else None
    logo_cell = logo_img if logo_img is not None else Spacer(1, logo_mm)
    logo_wrap = Table([[Spacer(1, 1), logo_cell]], colWidths=[5 * mm, 28 * mm])
    logo_wrap.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    header_text = Table(
        [
            [Paragraph(escape(current_tenant().university_name), style_uni)],
            [Paragraph(escape(current_tenant().name), style_sub)],
            [Paragraph(escape(_rl_safe_text(cycle.name if cycle else 'Admission')), style_sub)],
        ],
        colWidths=[content_w - 66 * mm],
    )
    header_text.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    header_block = Table(
        [[logo_wrap, header_text, Spacer(1, logo_mm)]],
        colWidths=[33 * mm, content_w - 66 * mm, 33 * mm],
    )
    header_block.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LINEBELOW', (0, 0), (-1, -1), 0.6, navy),
    ]))

    body = [
        header_block,
        Spacer(1, 2 * mm),
        title_wrap,
        head_row,
        Spacer(1, 1.5 * mm),
    ]
    for section in ctx['sections']:
        body.append(Paragraph(f"{section['number']}. {section['title']}", style_sec))
        if section['kind'] == 'academic' and academic_table is not None:
            body.append(academic_table)
            continue
        kv_rows = []
        for row in section.get('rows') or []:
            val_style = style_value_bn if row.get('is_bangla') else style_value
            kv_rows.append([_p(row['label'], style_label), _p(row['value'], val_style)])
        if kv_rows:
            body.append(_section_table(kv_rows))

    body.append(Paragraph(f"{ctx['declaration_number']}. Declaration", style_sec))
    for para in ctx['declaration_paras']:
        body.append(Paragraph(escape(_rl_safe_text(para)), style_decl))

    verifier_name = ctx['verifier_name']
    sig_col_w = 80 * mm
    sig_row = Table(
        [[
            _app_sign_column(
                'Signature of the Applicant',
                candidate_sig_src,
                cache_name=f'form_{candidate.id}_candidate_sig.jpg',
                col_w=sig_col_w,
            ),
            _app_sign_column(
                'Signature of the Scrutinizer',
                scrutinizer_sig_src,
                cache_name=f'form_{candidate.id}_scrutinizer_sig.jpg',
                sublabel=verifier_name,
                col_w=sig_col_w,
            ),
        ]],
        colWidths=[content_w / 2.0, content_w / 2.0],
    )
    sig_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    body.append(sig_row)
    body.append(Paragraph(
        escape(_rl_safe_text(
            'This is a system-generated copy of the admission application submitted through '
            f'the {current_tenant().name} Academic Management System, {current_tenant().university_name}.'
        )),
        style_foot,
    ))

    def _draw_border(canvas_obj, _doc):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(navy)
        canvas_obj.setLineWidth(1.2)
        canvas_obj.rect(10 * mm, 10 * mm, A4[0] - 20 * mm, A4[1] - 20 * mm, stroke=1, fill=0)
        canvas_obj.restoreState()

    doc.build(body, onFirstPage=_draw_border, onLaterPages=_draw_border)
    return buffer.getvalue()


def _render_attachment_label_page(tag, filename=None):
    """Small cover page naming an attached certificate/transcript."""
    from xml.sax.saxutils import escape
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=40 * mm, bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'AttTitle', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=14, alignment=TA_CENTER, spaceAfter=8,
    )
    sub = ParagraphStyle(
        'AttSub', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=11, alignment=TA_CENTER, textColor=rl_colors.HexColor('#444444'),
    )
    flow = [
        Paragraph(escape(_rl_safe_text('Attached Academic Document')), title),
        Spacer(1, 6 * mm),
        Paragraph(escape(_rl_safe_text(tag or 'Document')), title),
    ]
    if filename:
        flow.append(Spacer(1, 4 * mm))
        flow.append(Paragraph(escape(_rl_safe_text(filename)), sub))
    doc.build(flow)
    return buf.getvalue()


def _render_image_document_pdf(abs_path, tag, filename=None):
    """One-page PDF with tag heading + image (certificate photo)."""
    from xml.sax.saxutils import escape
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    style_h = ParagraphStyle(
        'ImgDocH', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=12, alignment=TA_CENTER, spaceAfter=6,
    )
    style_s = ParagraphStyle(
        'ImgDocS', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=9, alignment=TA_CENTER, spaceAfter=8,
    )
    flow = [Paragraph(escape(_rl_safe_text(tag or 'Document')), style_h)]
    if filename:
        flow.append(Paragraph(escape(_rl_safe_text(filename)), style_s))
    img = _reportlab_flowable_image(
        abs_path, 170 * mm, 220 * mm,
        label='doc_attach',
        cache_name=f'doc_img_{abs(hash(abs_path)) % 10**10}.jpg',
    )
    if img is not None:
        flow.append(img)
    else:
        flow.append(Paragraph(escape('Image could not be embedded.'), style_s))
    doc.build(flow)
    return buf.getvalue()


def _pypdf_merger_class():
    """PdfMerger on PyPDF2 2+/3; PdfFileMerger on 1.26 (production pin)."""
    try:
        from PyPDF2 import PdfMerger
        return PdfMerger
    except ImportError:
        from PyPDF2 import PdfFileMerger
        return PdfFileMerger


def _pypdf_reader_class():
    try:
        from PyPDF2 import PdfReader
        return PdfReader
    except ImportError:
        from PyPDF2 import PdfFileReader
        return PdfFileReader


def _pdf_page_count(reader):
    if hasattr(reader, 'pages'):
        try:
            return len(reader.pages)
        except Exception:
            pass
    if hasattr(reader, 'getNumPages'):
        return reader.getNumPages()
    return 0


def _pdf_reader_from_bytes(pdf_bytes):
    """Open PDF bytes with PyPDF2 1.26+ (PdfFileReader / PdfReader)."""
    Reader = _pypdf_reader_class()
    stream = io.BytesIO(pdf_bytes)
    try:
        reader = Reader(stream, strict=False)
    except TypeError:
        reader = Reader(stream)
    encrypted = False
    if hasattr(reader, 'is_encrypted'):
        try:
            encrypted = bool(reader.is_encrypted)
        except Exception:
            encrypted = False
    elif hasattr(reader, 'isEncrypted'):
        try:
            encrypted = bool(reader.isEncrypted)
        except Exception:
            encrypted = False
    if encrypted:
        try:
            reader.decrypt('')
        except Exception:
            pass
    return reader


def _rasterize_pdf_with_external_tools(abs_path):
    """Fallback: convert PDF pages to JPEGs via pdftoppm or Ghostscript (if installed).

    Returns (image_paths, temp_dir_to_cleanup). temp_dir is None when no images.
    """
    import glob
    import shutil
    import subprocess
    import tempfile

    abs_path = os.path.abspath(abs_path)
    if not os.path.isfile(abs_path):
        return [], None

    tmp = tempfile.mkdtemp(prefix='adm_pdf_')
    images = []
    try:
        pdftoppm = shutil.which('pdftoppm')
        gs = shutil.which('gs') or shutil.which('gswin64c') or shutil.which('gswin32c')
        if pdftoppm:
            prefix = os.path.join(tmp, 'page')
            subprocess.run(
                [pdftoppm, '-jpeg', '-r', '120', abs_path, prefix],
                check=True, capture_output=True, timeout=120,
            )
            images = sorted(glob.glob(prefix + '*.jpg'))
        elif gs:
            out_pattern = os.path.join(tmp, 'page-%03d.jpg')
            subprocess.run(
                [
                    gs, '-dSAFER', '-dBATCH', '-dNOPAUSE', '-dQUIET',
                    '-sDEVICE=jpeg', '-r120',
                    f'-sOutputFile={out_pattern}',
                    abs_path,
                ],
                check=True, capture_output=True, timeout=120,
            )
            images = sorted(glob.glob(os.path.join(tmp, 'page-*.jpg')))
        if not images:
            shutil.rmtree(tmp, ignore_errors=True)
            return [], None
        return images, tmp
    except Exception:
        current_app.logger.exception('External PDF rasterize failed for %s', abs_path)
        shutil.rmtree(tmp, ignore_errors=True)
        return [], None


def _render_pdf_attachment_as_images(abs_path, tag, filename=None):
    """Build a ReportLab PDF from rasterized pages of an uploaded PDF."""
    import shutil

    images, tmp = _rasterize_pdf_with_external_tools(abs_path)
    if not images:
        return None
    from xml.sax.saxutils import escape
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, PageBreak

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    style_h = ParagraphStyle(
        'PdfAttH', parent=styles['Normal'], fontName='Times-Bold',
        fontSize=12, alignment=TA_CENTER, spaceAfter=6,
    )
    style_s = ParagraphStyle(
        'PdfAttS', parent=styles['Normal'], fontName='Times-Roman',
        fontSize=9, alignment=TA_CENTER, spaceAfter=8,
    )
    flow = [Paragraph(escape(_rl_safe_text(tag or 'Document')), style_h)]
    if filename:
        flow.append(Paragraph(escape(_rl_safe_text(filename)), style_s))
    for i, img_path in enumerate(images):
        if i:
            flow.append(PageBreak())
            flow.append(Paragraph(
                escape(_rl_safe_text(f'{tag or "Document"} (page {i + 1})')), style_s
            ))
        img = _reportlab_flowable_image(
            img_path, 180 * mm, 240 * mm,
            label='pdf_page',
            cache_name=f'pdf_raster_{os.path.basename(img_path)}',
        )
        if img is not None:
            flow.append(img)
    try:
        doc.build(flow)
        return buf.getvalue()
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _attachment_pdf_parts_for_candidate(candidate):
    """Build PDF byte chunks for each uploaded academic document.

    PDF uploads: cover page + raw file bytes (merged later via PdfFileMerger).
    Images: one ReportLab page with the image embedded.
    """
    parts = []
    docs = candidate.documents.order_by(AdmissionCandidateDocument.id).all()
    for doc in docs:
        path = _document_abs_path(doc)
        if not path:
            current_app.logger.warning(
                'Document %s for %s missing on disk (path=%r)',
                doc.id, candidate.application_id, getattr(doc, 'file_path', None),
            )
            continue
        ext = path.rsplit('.', 1)[-1].lower()
        tag = doc.tag or 'Document'
        fname = doc.original_filename or os.path.basename(path)
        try:
            if ext == 'pdf':
                with open(path, 'rb') as fh:
                    pdf_bytes = fh.read()
                if not pdf_bytes:
                    parts.append(_render_attachment_label_page(f'{tag} (empty file)', fname))
                    continue
                # Cover + original PDF as separate merge parts (PyPDF2 1.26-safe)
                cover = _render_attachment_label_page(tag, fname)
                try:
                    n_pages = _pdf_page_count(_pdf_reader_from_bytes(pdf_bytes))
                    if n_pages < 1:
                        raise ValueError('PDF has no pages')
                    parts.append(cover)
                    parts.append(pdf_bytes)
                except Exception:
                    current_app.logger.exception(
                        'PDF attachment unreadable %s for %s; trying rasterize',
                        doc.id, candidate.application_id,
                    )
                    raster = _render_pdf_attachment_as_images(path, tag, fname)
                    if raster:
                        parts.append(raster)
                    else:
                        parts.append(_render_attachment_label_page(
                            f'{tag} — PDF could not be embedded (unsupported or encrypted). '
                            f'Re-upload as JPG/PNG if needed.',
                            fname,
                        ))
            elif ext in ('jpg', 'jpeg', 'png'):
                parts.append(_render_image_document_pdf(path, tag, fname))
            else:
                parts.append(_render_attachment_label_page(f'{tag} (unsupported file type)', fname))
        except Exception:
            current_app.logger.exception(
                'Failed to attach document %s for %s', doc.id, candidate.application_id
            )
            parts.append(_render_attachment_label_page(f'{tag} (could not attach)', fname))
    return parts


def _render_application_package_pdf(candidate):
    """Application form PDF + appended certificate/transcript attachments.

    Returns ``(pdf_bytes, engine_tag)``.
    """
    form_pdf, engine = _render_application_form_pdf(candidate)
    try:
        parts = [form_pdf] + _attachment_pdf_parts_for_candidate(candidate)
        if len(parts) == 1:
            return form_pdf, engine
        return _merge_pdf_bytes_list(parts), engine
    except Exception:
        current_app.logger.exception(
            'Attachment merge failed for %s; returning form PDF only',
            candidate.application_id,
        )
        return form_pdf, engine


def _all_cycle_candidates(cycle):
    """Every candidate in the cycle — no payment / status / roll / search filter."""
    return (
        AdmissionCandidate.query
        .filter_by(cycle_id=cycle.id)
        .order_by(AdmissionCandidate.application_id)
        .all()
    )


def _filter_cycle_candidates(cycle):
    """Apply the same filters as the candidates list page (GET args or form)."""
    q = AdmissionCandidate.query.filter_by(cycle_id=cycle.id)
    payment = request.values.get('payment') or ''
    status = request.values.get('status') or ''
    search = (request.values.get('search') or '').strip()
    if payment in PAYMENT_STATUSES:
        q = q.filter_by(payment_status=payment)
    if status in APPLICATION_STATUSES:
        q = q.filter_by(application_status=status)
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(
            AdmissionCandidate.full_name.ilike(like),
            AdmissionCandidate.application_id.ilike(like),
            AdmissionCandidate.phone.ilike(like),
            AdmissionCandidate.roll_no.ilike(like),
            AdmissionCandidate.rocket_txn_id.ilike(like),
            AdmissionCandidate.bank_slip_txn_no.ilike(like),
        ))
    return q.order_by(AdmissionCandidate.application_id).all(), payment, status, search


def _merge_pdf_bytes_list(pdf_list):
    """Merge PDF byte-strings. Uses PdfFileMerger (works on PyPDF2==1.26.0)."""
    Merger = _pypdf_merger_class()
    merger = Merger()
    appended = 0
    try:
        for pdf_bytes in pdf_list:
            if not pdf_bytes:
                continue
            try:
                merger.append(io.BytesIO(pdf_bytes))
                appended += 1
            except Exception:
                current_app.logger.exception('Skipping unreadable PDF chunk during merge')
        if appended == 0:
            for pdf_bytes in pdf_list:
                if pdf_bytes:
                    return pdf_bytes
            return b''
        out = io.BytesIO()
        merger.write(out)
        return out.getvalue()
    finally:
        try:
            merger.close()
        except Exception:
            pass

def _zip_pdf_bytes(named_pdfs):
    """Build a ZIP (filename -> pdf bytes). Deduplicate names inside the archive."""
    import zipfile
    buf = io.BytesIO()
    used = {}
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for name, pdf_bytes in named_pdfs:
            if not pdf_bytes:
                continue
            base = name or 'application.pdf'
            if base in used:
                used[base] += 1
                if '.' in base:
                    stem, ext = base.rsplit('.', 1)
                else:
                    stem, ext = base, 'pdf'
                out_name = f'{stem}_{used[base]}.{ext}'
            else:
                used[base] = 0
                out_name = base
            zf.writestr(out_name, pdf_bytes)
    buf.seek(0)
    return buf


def _safe_pdf_filename(candidate, prefix='application', engine=None):
    """Build a clean download name (engine tag is intentionally omitted from the filename)."""
    app_id = re.sub(r'[^A-Za-z0-9_-]+', '_', candidate.application_id or str(candidate.id))
    return f'{prefix}_{app_id}.pdf'


def _roll_numeric_part(roll_no, prefix):
    """Numeric tail of an assigned roll (after stripping the cycle prefix)."""
    if not roll_no:
        return None
    tail = roll_no[len(prefix):] if prefix and roll_no.startswith(prefix) else roll_no
    m = re.search(r'(\d+)$', tail)
    return int(m.group(1)) if m else None


# ===========================================================================
# PUBLIC (candidate) SIDE
# ===========================================================================

@admission_exam_bp.route('/apply/<token>')
def landing(token):
    cycle, disabled = _public_cycle_by_token(token)
    if disabled:
        return disabled
    payload = _parse_landing_payload(cycle.instructions)
    sections = [
        {
            'title': s['title'],
            'body': s['body'],
            'body_html': _landing_body_markup(s['body']),
        }
        for s in payload['sections']
    ]
    return render_template(
        'admission_exam/landing.html',
        cycle=cycle,
        candidate=_current_candidate(token),
        landing_sections=sections,
        landing_attachments=payload['attachments'],
        format_file_size=_format_file_size,
        enabled_payment_methods=cycle.enabled_payment_methods(),
        payment_method_labels=PAYMENT_METHOD_LABELS,
        payment_accounts=_payment_accounts_map(cycle),
        mfs_payment_methods=sorted(MFS_PAYMENT_METHODS),
    )


@admission_exam_bp.route('/apply/<token>/form', methods=['GET', 'POST'])
@csrf.exempt
def apply_form(token):
    cycle, disabled = _public_cycle_by_token(token)
    if disabled:
        return disabled
    if not cycle.is_application_open:
        flash(cycle.application_closed_reason or 'Applications are currently closed for this admission cycle.', 'warning')
        return redirect(url_for('admission_exam.landing', token=token))

    schema = get_field_schema(cycle)
    form_fields = form_input_fields(cycle)
    enabled_methods = cycle.enabled_payment_methods()
    on_form_fields = fields_where(cycle, 'on_form')
    photo_required = any(f.get('key') == 'photo' and f.get('required') for f in on_form_fields)
    signature_required = any(
        f.get('key') == 'candidate_signature' and f.get('required') for f in on_form_fields
    )
    show_academic = academic_form_enabled(cycle)

    def _render_apply(form_data):
        return render_template(
            'admission_exam/apply_form.html',
            cycle=cycle,
            form_fields=form_fields,
            field_schema=schema,
            photo_required=photo_required,
            signature_required=signature_required,
            show_academic=show_academic,
            academic_exam_rows=ACADEMIC_EXAM_ROWS,
            academic_col_suffixes=ACADEMIC_COL_SUFFIXES,
            extra_field_defs=extra_field_defs(cycle),
            form=form_data,
            enabled_payment_methods=enabled_methods,
            payment_method_labels=PAYMENT_METHOD_LABELS,
            mfs_payment_methods=sorted(MFS_PAYMENT_METHODS),
            payment_accounts=_payment_accounts_map(cycle),
            bank_slip_max_label=BANK_SLIP_MAX_SIZE_LABEL,
            document_tags=get_document_tags(cycle),
            document_max_label=DOCUMENT_MAX_LABEL,
            declaration_text=get_declaration_text(cycle),
            academic_extra_rows=collect_academic_extra_rows(form_data)
            if hasattr(form_data, 'getlist') else [],
        )

    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip().upper()
        phone = (request.form.get('phone') or '').strip()
        email = (request.form.get('email') or '').strip()
        payment_method = _normalize_payment_method(request.form.get('payment_method'), cycle)
        mfs_labels = mfs_field_labels(payment_method)
        rocket_txn_id = (request.form.get('rocket_txn_id') or '').strip()
        rocket_sender_phone = (request.form.get('rocket_sender_phone') or '').strip()
        bank_slip_txn_no = (request.form.get('bank_slip_txn_no') or '').strip()
        photo = request.files.get('photo')
        bank_slip = request.files.get('bank_slip')
        candidate_signature = request.files.get('candidate_signature')

        errors = []
        for field in form_fields:
            if not field.get('required'):
                continue
            key = field['key']
            if key in FILE_FIELD_KEYS or key in PAYMENT_FIELD_KEYS:
                continue
            val = (request.form.get(key) or '').strip()
            if not val:
                errors.append(f'{field.get("label") or key} is required.')
        if photo_required and (not photo or not photo.filename):
            errors.append('A passport-size photo is required.')
        if signature_required and (not candidate_signature or not candidate_signature.filename):
            errors.append('Signature of the applicant is required.')
        if is_mfs_payment_method(payment_method):
            if not rocket_txn_id:
                errors.append(f'{mfs_labels["txn"]} is required.')
            if not rocket_sender_phone:
                errors.append(f'{mfs_labels["sender"]} is required.')
        elif payment_method == 'agrani_bank':
            if not bank_slip_txn_no:
                errors.append('Bank slip / transaction number is required.')
            if not bank_slip or not bank_slip.filename:
                errors.append('Please upload a photo of the Agrani Bank deposit slip.')

        # Peek document uploads (require ≥1); save after application_id is known
        doc_files = request.files.getlist('doc_file')
        has_doc = any(f and f.filename for f in doc_files)
        if not has_doc:
            errors.append(
                'Please upload attested photocopies of academic certificates and transcripts '
                '(at least one file).'
            )

        if errors:
            for e in errors:
                flash(e, 'danger')
            return _render_apply(request.form)

        application_id = _generate_application_id(cycle)
        photo_path = None
        if photo and photo.filename:
            photo_path, photo_err = _save_photo(cycle, application_id, photo)
            if photo_err:
                flash(photo_err, 'danger')
                return _render_apply(request.form)

        signature_path = None
        if candidate_signature and candidate_signature.filename:
            signature_path, sig_err = _save_candidate_signature(
                cycle, application_id, candidate_signature
            )
            if sig_err:
                flash(sig_err, 'danger')
                return _render_apply(request.form)

        bank_slip_path = None
        if payment_method == 'agrani_bank' and bank_slip and bank_slip.filename:
            bank_slip_path, slip_err = _save_bank_slip(cycle, application_id, bank_slip)
            if slip_err:
                flash(slip_err, 'danger')
                return _render_apply(request.form)

        docs, doc_err = _collect_document_uploads(
            cycle, application_id, request.form, request.files
        )
        if doc_err:
            flash(doc_err, 'danger')
            return _render_apply(request.form)
        if not docs:
            flash(
                'Please upload attested photocopies of academic certificates and transcripts.',
                'danger',
            )
            return _render_apply(request.form)

        use_mfs = is_mfs_payment_method(payment_method)
        pin = _generate_pin()
        candidate = AdmissionCandidate(
            cycle_id=cycle.id,
            application_id=application_id,
            full_name=full_name or 'Applicant',
            phone=phone or '-',
            email=email or None,
            photo_path=photo_path,
            signature_path=signature_path,
            extra_fields=json.dumps(
                _collect_extra_fields(request.form, cycle=cycle), ensure_ascii=False
            ),
            payment_method=payment_method,
            rocket_txn_id=rocket_txn_id or None if use_mfs else None,
            rocket_sender_phone=rocket_sender_phone or None if use_mfs else None,
            bank_slip_txn_no=bank_slip_txn_no or None if payment_method == 'agrani_bank' else None,
            bank_slip_path=bank_slip_path if payment_method == 'agrani_bank' else None,
            payment_status='pending',
            application_status='submitted',
        )
        candidate.set_pin(pin)
        db.session.add(candidate)
        db.session.flush()
        for doc in docs:
            db.session.add(AdmissionCandidateDocument(
                candidate_id=candidate.id,
                tag=doc['tag'],
                file_path=doc['file_path'],
                original_filename=doc['original_filename'],
                status='pending',
            ))
        db.session.commit()

        session.permanent = True
        session[CANDIDATE_SESSION_KEY] = candidate.id
        return render_template('admission_exam/confirmation.html', cycle=cycle,
                               candidate=candidate, pin=pin,
                               payment_method_labels=PAYMENT_METHOD_LABELS)

    return _render_apply({})


@admission_exam_bp.route('/apply/<token>/login', methods=['GET', 'POST'])
@csrf.exempt
def candidate_login(token):
    cycle, disabled = _public_cycle_by_token(token)
    if disabled:
        return disabled
    if _current_candidate(token):
        return redirect(url_for('admission_exam.candidate_dashboard', token=token))

    if request.method == 'POST':
        application_id = (request.form.get('application_id') or '').strip().upper()
        pin = (request.form.get('pin') or '').strip()
        candidate = AdmissionCandidate.query.filter_by(application_id=application_id).first()
        if candidate and candidate.cycle_id == cycle.id and candidate.check_pin(pin):
            session.permanent = True
            session[CANDIDATE_SESSION_KEY] = candidate.id
            return redirect(url_for('admission_exam.candidate_dashboard', token=token))
        flash('Invalid Application ID or PIN.', 'danger')

    return render_template('admission_exam/candidate_login.html', cycle=cycle)


@admission_exam_bp.route('/apply/<token>/logout')
def candidate_logout(token):
    session.pop(CANDIDATE_SESSION_KEY, None)
    return redirect(url_for('admission_exam.landing', token=token))


@admission_exam_bp.route('/apply/<token>/dashboard')
@candidate_required
def candidate_dashboard(cycle, candidate):
    # Fresh read so publish/roll/payment flags are not stale; avoid browser caching the HTML.
    db.session.refresh(candidate)
    db.session.refresh(cycle)
    can_download = candidate.can_download_admit
    extra = _parse_extra_fields(candidate)
    resp = make_response(render_template(
        'admission_exam/candidate_dashboard.html',
        cycle=cycle,
        candidate=candidate,
        can_download_admit=can_download,
        extra=extra,
        academic_rows=academic_display_rows(extra),
        academic_extra_rows=parse_academic_extra_rows(extra),
        academic_col_suffixes=ACADEMIC_COL_SUFFIXES,
        documents=candidate.documents.order_by(AdmissionCandidateDocument.id).all(),
        document_tags=get_document_tags(cycle),
        document_max_label=DOCUMENT_MAX_LABEL,
        extra_field_defs=personal_extra_field_defs(cycle),
        display_fields=[f for f in form_input_fields(cycle) if f.get('key') not in PAYMENT_FIELD_KEYS],
        enabled_payment_methods=cycle.enabled_payment_methods(),
        payment_method_labels=PAYMENT_METHOD_LABELS,
        mfs_payment_methods=sorted(MFS_PAYMENT_METHODS),
        payment_accounts=_payment_accounts_map(cycle),
        mfs_labels=mfs_field_labels(candidate.payment_method),
        bank_slip_max_label=BANK_SLIP_MAX_SIZE_LABEL,
    ))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@admission_exam_bp.route('/apply/<token>/payment', methods=['POST'])
@csrf.exempt
@candidate_required
def candidate_update_payment(cycle, candidate):
    """Candidate may correct payment info while pending or after rejection."""
    if candidate.payment_status == 'verified':
        flash('Payment is already verified; it can no longer be changed.', 'warning')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))

    payment_method = _normalize_payment_method(
        request.form.get('payment_method') or candidate.payment_method, cycle
    )
    if is_mfs_payment_method(payment_method):
        labels = mfs_field_labels(payment_method)
        rocket_txn_id = (request.form.get('rocket_txn_id') or '').strip()
        rocket_sender_phone = (request.form.get('rocket_sender_phone') or '').strip()
        if not rocket_txn_id or not rocket_sender_phone:
            flash(f'Both {labels["txn"]} and {labels["sender"]} are required.', 'danger')
            return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
        candidate.payment_method = payment_method
        candidate.rocket_txn_id = rocket_txn_id
        candidate.rocket_sender_phone = rocket_sender_phone
        candidate.bank_slip_txn_no = None
        candidate.bank_slip_path = None
    else:
        bank_slip_txn_no = (request.form.get('bank_slip_txn_no') or '').strip()
        bank_slip = request.files.get('bank_slip')
        if not bank_slip_txn_no:
            flash('Bank slip / transaction number is required.', 'danger')
            return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
        if bank_slip and bank_slip.filename:
            slip_path, slip_err = _save_bank_slip(cycle, candidate.application_id, bank_slip)
            if slip_err:
                flash(slip_err, 'danger')
                return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
            candidate.bank_slip_path = slip_path
        elif not candidate.bank_slip_path:
            flash('Please upload a photo of the Agrani Bank deposit slip.', 'danger')
            return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
        candidate.payment_method = 'agrani_bank'
        candidate.bank_slip_txn_no = bank_slip_txn_no
        candidate.rocket_txn_id = None
        candidate.rocket_sender_phone = None

    candidate.payment_status = 'pending'
    candidate.payment_note = None
    candidate.verified_by = None
    candidate.verified_at = None
    db.session.commit()
    flash('Payment information updated. It will be verified by the committee.', 'success')
    return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))


@admission_exam_bp.route('/apply/<token>/photo')
@candidate_required
def candidate_photo(cycle, candidate):
    path = _photo_abs_path(candidate)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/apply/<token>/signature')
@candidate_required
def candidate_signature_image(cycle, candidate):
    path = _candidate_signature_abs_path(candidate)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/apply/<token>/signature', methods=['POST'])
@csrf.exempt
@candidate_required
def candidate_update_signature(cycle, candidate):
    """Allow candidate to upload/replace signature while payment is not verified."""
    if candidate.payment_status == 'verified':
        flash('Payment is already verified; signature can no longer be changed.', 'warning')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    file_storage = request.files.get('candidate_signature')
    if not file_storage or not file_storage.filename:
        flash('Please choose a signature image to upload.', 'danger')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    path, err = _save_candidate_signature(cycle, candidate.application_id, file_storage)
    if err:
        flash(err, 'danger')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    candidate.signature_path = path
    db.session.commit()
    flash('Signature updated.', 'success')
    return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))


@admission_exam_bp.route('/apply/<token>/bank-slip')
@candidate_required
def candidate_bank_slip(cycle, candidate):
    path = _bank_slip_abs_path(candidate)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/apply/<token>/document/<int:doc_id>')
@candidate_required
def candidate_document_file(cycle, candidate, doc_id):
    doc = AdmissionCandidateDocument.query.filter_by(
        id=doc_id, candidate_id=candidate.id
    ).first_or_404()
    path = _document_abs_path(doc)
    if not path:
        abort(404)
    return send_file(path, download_name=doc.original_filename or os.path.basename(path))


@admission_exam_bp.route('/apply/<token>/documents', methods=['POST'])
@csrf.exempt
@candidate_required
def candidate_add_documents(cycle, candidate):
    """Candidate may add more certificates while payment is not verified."""
    if candidate.payment_status == 'verified':
        flash('Payment is already verified; documents can no longer be changed.', 'warning')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    docs, doc_err = _collect_document_uploads(
        cycle, candidate.application_id, request.form, request.files
    )
    if doc_err:
        flash(doc_err, 'danger')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    if not docs:
        flash('Please choose at least one document to upload.', 'danger')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    for doc in docs:
        db.session.add(AdmissionCandidateDocument(
            candidate_id=candidate.id,
            tag=doc['tag'],
            file_path=doc['file_path'],
            original_filename=doc['original_filename'],
            status='pending',
        ))
    db.session.commit()
    flash(f'{len(docs)} document(s) uploaded.', 'success')
    return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))


@admission_exam_bp.route('/apply/<token>/document/<int:doc_id>/delete', methods=['POST'])
@csrf.exempt
@candidate_required
def candidate_delete_document(cycle, candidate, doc_id):
    if candidate.payment_status == 'verified':
        flash('Payment is already verified; documents can no longer be changed.', 'warning')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    doc = AdmissionCandidateDocument.query.filter_by(
        id=doc_id, candidate_id=candidate.id
    ).first_or_404()
    remaining = candidate.documents.count()
    if remaining <= 1:
        flash('At least one academic document is required. Upload a replacement first.', 'danger')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    db.session.delete(doc)
    db.session.commit()
    flash('Document removed.', 'success')
    return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))


def _admit_pdf_response(pdf_bytes, download_name):
    """Serve PDF inline (https://… not file:// Downloads) with no-cache headers."""
    # Inline so Chrome/Acrobat opens the live URL; avoids stale Downloads copies.
    resp = make_response(send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=download_name,
    ))
    resp.headers['X-Admit-Engine'] = ADMIT_PDF_ENGINE
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@admission_exam_bp.route('/apply/<token>/admit-card.pdf')
@candidate_required
def candidate_admit_card(cycle, candidate):
    if not candidate.can_download_admit:
        flash('Your admit card is not available yet.', 'warning')
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    try:
        pdf_bytes = _render_admit_card_pdf(candidate)
    except Exception as e:
        current_app.logger.exception('Admit card PDF failed for %s: %s', candidate.application_id, e)
        # Surface short error so cPanel debugging is possible without log access
        err = _rl_safe_text(str(e), 'unknown error')[:180]
        flash(
            f'Could not generate admit card ({type(e).__name__}: {err}). '
            'Please try again or contact the committee.',
            'danger',
        )
        return redirect(url_for('admission_exam.candidate_dashboard', token=cycle.public_token))
    stamp = datetime.utcnow().strftime('%H%M%S')
    return _admit_pdf_response(
        pdf_bytes,
        f"admit_{candidate.roll_no or candidate.application_id}_{stamp}.pdf",
    )


# ===========================================================================
# COMMITTEE / ADMIN SIDE
# ===========================================================================

@admission_exam_bp.route('/')
@login_required
def index():
    if not user_can_access_admission():
        flash('You do not have access to the Admission Exam module.', 'danger')
        abort(403)
    from utils.dashboard_settings import require_officer_dashboard_card
    blocked = require_officer_dashboard_card('admission_exam')
    if blocked:
        return blocked
    if _user_is_manager():
        cycles = AdmissionCycle.query.order_by(AdmissionCycle.created_at.desc()).all()
    else:
        ids = _user_committee_cycle_ids()
        cycles = (AdmissionCycle.query.filter(AdmissionCycle.id.in_(ids))
                  .order_by(AdmissionCycle.created_at.desc()).all()) if ids else []
    stats = {}
    for c in cycles:
        stats[c.id] = {
            'total': c.candidates.count(),
            'verified': c.candidates.filter_by(payment_status='verified').count(),
            'selected': c.candidates.filter_by(application_status='selected').count(),
        }
    return render_template('admission_exam/admin_cycles.html', cycles=cycles,
                           stats=stats, can_create=_user_is_manager())


@admission_exam_bp.route('/cycle/new', methods=['POST'])
@login_required
def cycle_new():
    if not _user_is_manager():
        flash('Only administrators and officers can create admission cycles.', 'danger')
        abort(403)
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Cycle name is required.', 'danger')
        return redirect(url_for('admission_exam.index'))
    app_id_prefix = (request.form.get('app_id_prefix') or current_tenant().app_id_prefix or 'APP').strip().upper() or 'APP'
    slug = _normalize_slug(request.form.get('public_slug'))
    if not slug:
        slug = _default_slug_from_prefix(app_id_prefix)
    if not _slug_available(slug):
        flash(f'Public link “{slug}” is already in use. Choose a different short link.', 'danger')
        return redirect(url_for('admission_exam.index'))
    cycle = AdmissionCycle(
        name=name,
        public_token=slug,
        status='draft',
        is_enabled=True,
        app_id_prefix=app_id_prefix,
        created_by=current_user.id,
    )
    db.session.add(cycle)
    db.session.commit()
    flash('Admission cycle created. Configure it, add committee members, then open applications.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>')
@login_required
@cycle_access_required
def cycle_detail(cycle):
    users = _committee_eligible_users()
    member_user_ids = {m.user_id for m in cycle.committee_members}
    counts = {
        'total': cycle.candidates.count(),
        'payment_pending': cycle.candidates.filter_by(payment_status='pending').count(),
        'payment_verified': cycle.candidates.filter_by(payment_status='verified').count(),
        'payment_rejected': cycle.candidates.filter_by(payment_status='rejected').count(),
        'selected': cycle.candidates.filter_by(application_status='selected').count(),
        'rolls_assigned': cycle.candidates.filter(AdmissionCandidate.roll_no.isnot(None)).count(),
    }
    public_url = url_for('admission_exam.landing', token=cycle.public_token, _external=True)
    landing_payload = _parse_landing_payload(cycle.instructions)
    landing_sections = landing_payload['sections']
    if not landing_sections:
        landing_sections = [
            {'title': 'Admission Conditions', 'body': ''},
            {'title': 'Guidelines', 'body': ''},
        ]
    return render_template('admission_exam/admin_cycle_detail.html', cycle=cycle,
                           enabled_payment_methods=cycle.enabled_payment_methods(),
                           payment_method_labels=PAYMENT_METHOD_LABELS,
                           payment_method_order=PAYMENT_METHOD_ORDER,
                           users=users, member_user_ids=member_user_ids,
                           counts=counts, public_url=public_url,
                           landing_sections=landing_sections,
                           landing_attachments=landing_payload['attachments'],
                           format_file_size=_format_file_size,
                           landing_file_max_label=LANDING_FILE_MAX_LABEL,
                           document_tags=get_document_tags(cycle),
                           declaration_text=get_declaration_text(cycle),
                           can_manage=_user_is_manager() or cycle.id in _user_committee_cycle_ids())


@admission_exam_bp.route('/cycle/<int:cycle_id>/document-tags', methods=['POST'])
@login_required
@cycle_access_required
def cycle_document_tags(cycle):
    """Save suggested certificate/transcript tags for this cycle."""
    if request.form.get('action') == 'reset_defaults':
        cycle.document_tags = serialize_document_tags(None)
        db.session.commit()
        flash('Document tags reset to defaults.', 'success')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    raw_lines = request.form.get('document_tags') or ''
    tags = [line.strip() for line in raw_lines.splitlines() if line.strip()]
    cycle.document_tags = serialize_document_tags(tags)
    db.session.commit()
    flash('Document upload tags saved.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/declaration', methods=['POST'])
@login_required
@cycle_access_required
def cycle_declaration(cycle):
    """Save customizable application-form declaration text."""
    if request.form.get('action') == 'reset_defaults':
        cycle.declaration_text = None
        db.session.commit()
        flash('Declaration text reset to default.', 'success')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    cycle.declaration_text = serialize_declaration_text(request.form.get('declaration_text'))
    db.session.commit()
    flash('Declaration text saved. It will appear on application form PDFs.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/field-schema', methods=['GET', 'POST'])
@login_required
@cycle_access_required
def cycle_field_schema(cycle):
    """Edit which fields appear on the application form, admit card, and PDFs."""
    if request.method == 'GET':
        return render_template(
            'admission_exam/admin_field_schema.html',
            cycle=cycle,
            field_schema=get_field_schema(cycle),
        )

    if request.form.get('action') == 'reset_defaults':
        cycle.field_schema = serialize_field_schema(default_field_schema())
        db.session.commit()
        flash('Form & admit card fields reset to defaults.', 'success')
        return redirect(url_for('admission_exam.cycle_field_schema', cycle_id=cycle.id))

    fields = parse_schema_from_form(request.form)
    cycle.field_schema = serialize_field_schema(fields)
    db.session.commit()
    flash('Form & admit card fields saved. Public form and PDFs will use this layout.', 'success')
    return redirect(url_for('admission_exam.cycle_field_schema', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/edit', methods=['POST'])
@login_required
@cycle_access_required
def cycle_edit(cycle):
    cycle.name = (request.form.get('name') or cycle.name).strip()
    cycle.fee_amount = (request.form.get('fee_amount') or '').strip() or None
    cycle.rocket_account_number = (request.form.get('rocket_account_number') or '').strip() or None
    cycle.bkash_account_number = (request.form.get('bkash_account_number') or '').strip() or None
    cycle.nagad_account_number = (request.form.get('nagad_account_number') or '').strip() or None
    cycle.agrani_account_number = (request.form.get('agrani_account_number') or '').strip() or None
    cycle.agrani_account_name = (request.form.get('agrani_account_name') or '').strip() or None
    cycle.agrani_routing_number = (request.form.get('agrani_routing_number') or '').strip() or None
    cycle.agrani_branch = (request.form.get('agrani_branch') or '').strip() or None
    cycle.payment_methods_enabled = _parse_enabled_payment_methods_from_form(request.form)
    cycle.app_id_prefix = (request.form.get('app_id_prefix') or 'APP').strip().upper() or 'APP'
    cycle.roll_prefix = (request.form.get('roll_prefix') or '').strip()
    try:
        cycle.roll_start = max(1, int(request.form.get('roll_start') or 1))
    except ValueError:
        pass
    try:
        pad = int(request.form.get('roll_pad_width') or 0)
        cycle.roll_pad_width = pad if pad in (0, 2, 3, 4, 5, 6) else 0
    except ValueError:
        cycle.roll_pad_width = 0
    cycle.apply_start = _parse_dt_local(request.form.get('apply_start'))
    cycle.apply_end = _parse_dt_local(request.form.get('apply_end'))
    cycle.exam_date = (request.form.get('exam_date') or '').strip() or None
    cycle.exam_venue = (request.form.get('exam_venue') or '').strip() or None
    db.session.commit()
    flash('Cycle settings saved.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/landing-content', methods=['POST'])
@login_required
@cycle_access_required
def cycle_landing_content(cycle):
    """Save conditions / guidelines / other sections shown on the public landing page."""
    payload = _parse_landing_payload(cycle.instructions)
    sections = _collect_landing_sections(request.form)
    cycle.instructions = _serialize_landing_payload(sections, payload['attachments'])
    db.session.commit()
    flash('Landing page content saved. It is now visible on the public application link.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/landing-file', methods=['POST'])
@login_required
@cycle_access_required
def cycle_landing_file_upload(cycle):
    """Upload a downloadable file for the public landing page."""
    upload = request.files.get('landing_file')
    if not upload or not upload.filename:
        flash('Please choose a file to upload.', 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))

    filename = secure_filename(upload.filename) or 'file'
    if '.' not in filename:
        flash('Invalid file name.', 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in LANDING_FILE_EXTS:
        flash(
            'File type not allowed. Use PDF, Word, Excel, PowerPoint, image, text, or ZIP.',
            'danger',
        )
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))

    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(0)
    if size <= 0:
        flash('Empty file.', 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    if size > LANDING_FILE_MAX_BYTES:
        flash(f'File is too large. Maximum is {LANDING_FILE_MAX_LABEL}.', 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))

    stored = f"{uuid.uuid4().hex}.{ext}"
    abs_dir = _landing_files_dir(cycle)
    abs_path = os.path.join(abs_dir, stored)
    upload.save(abs_path)
    rel_path = os.path.join(
        'static', 'uploads', 'admission_exam', f'cycle_{cycle.id}', 'landing_files', stored
    ).replace('\\', '/')

    payload = _parse_landing_payload(cycle.instructions)
    payload['attachments'].append({
        'id': uuid.uuid4().hex[:16],
        'name': filename[:180],
        'path': rel_path,
        'size': size,
    })
    cycle.instructions = _serialize_landing_payload(payload['sections'], payload['attachments'])
    db.session.commit()
    flash(f'File “{filename}” uploaded. It will appear on the public application page.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/landing-file/<file_id>/delete', methods=['POST'])
@login_required
@cycle_access_required
def cycle_landing_file_delete(cycle, file_id):
    payload = _parse_landing_payload(cycle.instructions)
    keep = []
    removed = None
    for item in payload['attachments']:
        if item['id'] == file_id:
            removed = item
        else:
            keep.append(item)
    if not removed:
        flash('File not found.', 'warning')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))

    abs_path = _landing_file_abs_path(removed.get('path'))
    if abs_path and os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass
    cycle.instructions = _serialize_landing_payload(payload['sections'], keep)
    db.session.commit()
    flash(f'File “{removed.get("name") or "attachment"}” removed.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/apply/<token>/file/<file_id>')
def landing_file_download(token, file_id):
    """Public download of a landing-page attachment."""
    cycle, disabled = _public_cycle_by_token(token)
    if disabled:
        return disabled
    attachments = _parse_landing_attachments(cycle.instructions)
    item = next((a for a in attachments if a['id'] == file_id), None)
    if not item:
        abort(404)
    abs_path = _landing_file_abs_path(item.get('path'))
    if not abs_path or not os.path.isfile(abs_path):
        abort(404)
    return send_file(
        abs_path,
        as_attachment=True,
        download_name=item.get('name') or os.path.basename(abs_path),
    )


@admission_exam_bp.route('/cycle/<int:cycle_id>/toggle-enabled', methods=['POST'])
@login_required
@cycle_access_required
def cycle_toggle_enabled(cycle):
    """Enable or disable the whole cycle (blocks public apply link when disabled)."""
    enabled = (request.form.get('enabled') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    cycle.is_enabled = enabled
    db.session.commit()
    if enabled:
        flash('Cycle enabled. The public link is available again (subject to Open/Closed status).', 'success')
    else:
        flash('Cycle disabled. The public application link is now unavailable.', 'warning')
    return redirect(request.referrer or url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/status', methods=['POST'])
@login_required
@cycle_access_required
def cycle_status(cycle):
    from .models import _bd_now_naive

    status = (request.form.get('status') or '').strip().lower()
    if status not in CYCLE_STATUSES:
        abort(400)
    cycle.status = status

    # Opening must actually open the public form. If the date window would still
    # block applicants, clear/adjust it and tell the admin why.
    if status == 'open':
        now = _bd_now_naive()
        notes = []
        start = cycle.apply_start
        end = cycle.apply_end
        if start is not None and getattr(start, 'tzinfo', None) is not None:
            start = start.replace(tzinfo=None)
        if end is not None and getattr(end, 'tzinfo', None) is not None:
            end = end.replace(tzinfo=None)
        if start and now < start:
            cycle.apply_start = None
            notes.append('cleared a future application start time')
        if end and now > end:
            cycle.apply_end = None
            notes.append('cleared a past application deadline')
        db.session.commit()
        msg = 'Applications are now open on the public link.'
        if notes:
            msg += ' Also ' + ' and '.join(notes) + ' so applicants are not blocked.'
        flash(msg, 'success')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))

    db.session.commit()
    flash(f'Applications are now {status}.' if status != 'draft' else 'Cycle set to draft.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/token/regenerate', methods=['POST'])
@login_required
@cycle_access_required
def cycle_regenerate_token(cycle):
    slug = _normalize_slug(request.form.get('public_slug'))
    if not slug or len(slug) < 3:
        flash('Enter a short link of at least 3 characters (letters, numbers, hyphens).', 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    if not _slug_available(slug, exclude_cycle_id=cycle.id):
        flash(f'Public link “{slug}” is already in use. Choose a different one.', 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    cycle.public_token = slug
    db.session.commit()
    flash('Public link updated. The previous link no longer works.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/committee/add', methods=['POST'])
@login_required
@cycle_access_required
def committee_add(cycle):
    if not _user_is_manager():
        flash('Only administrators and officers can change the committee.', 'danger')
        abort(403)
    try:
        user_id = int(request.form.get('user_id') or 0)
    except ValueError:
        user_id = 0
    position = (request.form.get('position') or 'member').strip()
    if position not in ('chairman', 'member', 'officer'):
        position = 'member'
    user = User.query.get(user_id)
    if not user or not _user_is_committee_eligible(user):
        flash('Select a teacher or officer account.', 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    if cycle.committee_members.filter_by(user_id=user.id).first():
        flash('This user is already a committee member.', 'warning')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    db.session.add(AdmissionCommitteeMember(cycle_id=cycle.id, user_id=user.id, position=position))
    db.session.commit()
    flash(f'{user.full_name} added to the committee.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/committee/<int:member_id>/remove', methods=['POST'])
@login_required
@cycle_access_required
def committee_remove(cycle, member_id):
    if not _user_is_manager():
        flash('Only administrators and officers can change the committee.', 'danger')
        abort(403)
    member = AdmissionCommitteeMember.query.get_or_404(member_id)
    if member.cycle_id != cycle.id:
        abort(404)
    db.session.delete(member)
    db.session.commit()
    flash('Committee member removed.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/delete', methods=['POST'])
@login_required
@cycle_access_required
def cycle_delete(cycle):
    if not _user_is_manager():
        flash('Only administrators and officers can delete a cycle.', 'danger')
        abort(403)
    db.session.delete(cycle)
    db.session.commit()
    flash('Admission cycle and all its candidates were deleted.', 'success')
    return redirect(url_for('admission_exam.index'))


# --- Candidates -----------------------------------------------------------

@admission_exam_bp.route('/cycle/<int:cycle_id>/candidates')
@login_required
@cycle_access_required
def candidates_list(cycle):
    candidates, payment, status, search = _filter_cycle_candidates(cycle)
    return render_template('admission_exam/admin_candidates.html', cycle=cycle,
                           candidates=candidates, payment=payment, status=status,
                           search=search)


@admission_exam_bp.route('/candidate/<int:candidate_id>')
@login_required
@candidate_access_required
def candidate_detail(candidate):
    extra = _parse_extra_fields(candidate)
    return render_template(
        'admission_exam/admin_candidate_detail.html',
        candidate=candidate,
        cycle=candidate.cycle,
        extra=extra,
        academic_rows=academic_display_rows(extra),
        academic_extra_rows=parse_academic_extra_rows(extra),
        academic_exam_rows=ACADEMIC_EXAM_ROWS,
        academic_col_suffixes=ACADEMIC_COL_SUFFIXES,
        show_academic=academic_form_enabled(candidate.cycle),
        documents=candidate.documents.order_by(AdmissionCandidateDocument.id).all(),
        document_tags=get_document_tags(candidate.cycle),
        document_max_label=DOCUMENT_MAX_LABEL,
        extra_field_defs=personal_extra_field_defs(candidate.cycle),
        field_schema=get_field_schema(candidate.cycle),
        form_fields=form_input_fields(candidate.cycle),
        payment_method_labels=PAYMENT_METHOD_LABELS,
        mfs_labels=mfs_field_labels(candidate.payment_method),
        is_mfs=is_mfs_payment_method(candidate.payment_method),
        my_signature_uploaded=bool(getattr(current_user, 'signature_path', None)),
        scrutinizer_sig_src=_user_signature_abs_path(candidate.verifier) if candidate.verifier else None,
    )


@admission_exam_bp.route('/candidate/<int:candidate_id>/photo')
@login_required
@candidate_access_required
def candidate_photo_admin(candidate):
    path = _photo_abs_path(candidate)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/candidate/<int:candidate_id>/signature')
@login_required
@candidate_access_required
def candidate_signature_admin(candidate):
    path = _candidate_signature_abs_path(candidate)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/candidate/<int:candidate_id>/bank-slip')
@login_required
@candidate_access_required
def candidate_bank_slip_admin(candidate):
    path = _bank_slip_abs_path(candidate)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/candidate/<int:candidate_id>/document/<int:doc_id>')
@login_required
@candidate_access_required
def candidate_document_admin(candidate, doc_id):
    doc = AdmissionCandidateDocument.query.filter_by(
        id=doc_id, candidate_id=candidate.id
    ).first_or_404()
    path = _document_abs_path(doc)
    if not path:
        abort(404)
    return send_file(path, download_name=doc.original_filename or os.path.basename(path))


@admission_exam_bp.route('/candidate/<int:candidate_id>/document/<int:doc_id>/verify', methods=['POST'])
@login_required
@candidate_access_required
def candidate_document_verify(candidate, doc_id):
    doc = AdmissionCandidateDocument.query.filter_by(
        id=doc_id, candidate_id=candidate.id
    ).first_or_404()
    action = (request.form.get('action') or '').strip()
    note = (request.form.get('note') or '').strip() or None
    if action == 'verify':
        doc.status = 'verified'
        doc.verified_by = current_user.id
        doc.verified_at = datetime.utcnow()
    elif action == 'reject':
        doc.status = 'rejected'
        doc.verified_by = current_user.id
        doc.verified_at = datetime.utcnow()
    elif action == 'reset':
        doc.status = 'pending'
        doc.verified_by = None
        doc.verified_at = None
    else:
        abort(400)
    doc.note = note
    db.session.commit()
    flash(f'Document “{doc.tag}” marked as {doc.status}.', 'success')
    return redirect(url_for('admission_exam.candidate_detail', candidate_id=candidate.id))


@admission_exam_bp.route('/candidate/<int:candidate_id>/payment', methods=['POST'])
@login_required
@candidate_access_required
def candidate_payment(candidate):
    action = (request.form.get('action') or '').strip()
    note = (request.form.get('note') or '').strip() or None
    if action == 'verify':
        candidate.payment_status = 'verified'
    elif action == 'reject':
        candidate.payment_status = 'rejected'
    elif action == 'reset':
        candidate.payment_status = 'pending'
    else:
        abort(400)
    candidate.payment_note = note
    # Scrutinizer on the application PDF = whichever committee member verifies from their login.
    candidate.verified_by = current_user.id if action in ('verify', 'reject') else None
    candidate.verified_at = datetime.utcnow() if action in ('verify', 'reject') else None
    db.session.commit()
    flash(f'Payment marked as {candidate.payment_status} for {candidate.application_id}.', 'success')
    if action == 'verify':
        if getattr(current_user, 'signature_path', None):
            flash(
                f'Your signature will appear as Scrutinizer on this application form PDF '
                f'({current_user.full_name}).',
                'info',
            )
        else:
            flash(
                'Upload your Scrutinizer signature (below, or on the cycle page) so it appears '
                'on the application form PDF for candidates you verify.',
                'warning',
            )
    return redirect(request.referrer or url_for('admission_exam.candidate_detail', candidate_id=candidate.id))


@admission_exam_bp.route('/candidate/<int:candidate_id>/set-scrutinizer', methods=['POST'])
@login_required
@candidate_access_required
def candidate_set_scrutinizer(candidate):
    """Mark the logged-in committee member as Scrutinizer for this application PDF."""
    candidate.verified_by = current_user.id
    if not candidate.verified_at:
        candidate.verified_at = datetime.utcnow()
    db.session.commit()
    if getattr(current_user, 'signature_path', None):
        flash(
            f'You ({current_user.full_name}) are set as Scrutinizer for {candidate.application_id}.',
            'success',
        )
    else:
        flash(
            'You are set as Scrutinizer, but you have not uploaded a signature yet. '
            'Upload it below so it appears on the PDF.',
            'warning',
        )
    return redirect(url_for('admission_exam.candidate_detail', candidate_id=candidate.id))


@admission_exam_bp.route('/candidate/<int:candidate_id>/select', methods=['POST'])
@login_required
@candidate_access_required
def candidate_select(candidate):
    status = (request.form.get('status') or '').strip()
    if status not in APPLICATION_STATUSES:
        abort(400)
    candidate.application_status = status
    db.session.commit()
    flash(f'Application {candidate.application_id} marked as {status}.', 'success')
    return redirect(request.referrer or url_for('admission_exam.candidate_detail', candidate_id=candidate.id))


@admission_exam_bp.route('/candidate/<int:candidate_id>/roll', methods=['POST'])
@login_required
@candidate_access_required
def candidate_roll(candidate):
    """Update or clear a candidate's roll number after bulk assign."""
    action = (request.form.get('action') or 'update').strip().lower()
    detail_url = url_for('admission_exam.candidate_detail', candidate_id=candidate.id)

    if action == 'clear':
        if not candidate.roll_no:
            flash('This candidate has no roll number to unassign.', 'info')
            return redirect(detail_url)
        old = candidate.roll_no
        candidate.roll_no = None
        db.session.commit()
        flash(f'Roll number {old} unassigned from {candidate.application_id}.', 'success')
        return redirect(detail_url)

    roll = (request.form.get('roll_no') or '').strip()
    if not roll:
        flash('Enter a roll number, or use Unassign to clear it.', 'danger')
        return redirect(detail_url)
    if len(roll) > 30:
        flash('Roll number is too long (max 30 characters).', 'danger')
        return redirect(detail_url)

    clash = (
        AdmissionCandidate.query
        .filter(
            AdmissionCandidate.cycle_id == candidate.cycle_id,
            AdmissionCandidate.roll_no == roll,
            AdmissionCandidate.id != candidate.id,
        )
        .first()
    )
    if clash:
        flash(
            f'Roll {roll} is already assigned to {clash.application_id}.',
            'danger',
        )
        return redirect(detail_url)

    candidate.roll_no = roll
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Could not save roll number (possible duplicate). Try again.', 'danger')
        return redirect(detail_url)
    flash(f'Roll number updated to {roll} for {candidate.application_id}.', 'success')
    return redirect(detail_url)


@admission_exam_bp.route('/cycle/<int:cycle_id>/candidates/bulk', methods=['POST'])
@login_required
@cycle_access_required
def candidates_bulk(cycle):
    action = (request.form.get('action') or '').strip()
    ids = request.form.getlist('candidate_ids')
    try:
        ids = [int(i) for i in ids]
    except ValueError:
        ids = []
    if not ids:
        flash('No candidates selected.', 'warning')
        return redirect(url_for('admission_exam.candidates_list', cycle_id=cycle.id))
    candidates = (
        AdmissionCandidate.query
        .filter(AdmissionCandidate.id.in_(ids), AdmissionCandidate.cycle_id == cycle.id)
        .order_by(AdmissionCandidate.application_id)
        .all()
    )

    if action in ('download_forms_pdf', 'download_forms_zip', 'download_admit_cards_pdf'):
        return _bulk_download_candidates_pdfs(cycle, candidates, action)

    if action == 'clear_rolls':
        cleared = 0
        for c in candidates:
            if c.roll_no:
                c.roll_no = None
                cleared += 1
        db.session.commit()
        flash(f'Unassigned roll numbers from {cleared} candidate(s).', 'success')
        return redirect(url_for('admission_exam.candidates_list', cycle_id=cycle.id))

    if action not in ('select', 'reject', 'verify_payment'):
        flash('Unknown bulk action.', 'danger')
        return redirect(url_for('admission_exam.candidates_list', cycle_id=cycle.id))

    for c in candidates:
        if action == 'select':
            c.application_status = 'selected'
        elif action == 'reject':
            c.application_status = 'rejected'
        elif action == 'verify_payment':
            c.payment_status = 'verified'
            c.verified_by = current_user.id
            c.verified_at = datetime.utcnow()
    db.session.commit()
    flash(f'{len(candidates)} candidate(s) updated.', 'success')
    if action == 'verify_payment':
        if getattr(current_user, 'signature_path', None):
            flash(
                f'You ({current_user.full_name}) are Scrutinizer on the verified forms.',
                'info',
            )
        else:
            flash(
                'Upload your Scrutinizer signature (cycle page or candidate page) '
                'so it appears on those application PDFs.',
                'warning',
            )
    return redirect(url_for('admission_exam.candidates_list', cycle_id=cycle.id))


def _bulk_download_candidates_pdfs(cycle, candidates, action):
    """Build merged PDF or ZIP for selected / filtered candidates."""
    if not candidates:
        flash('No candidates to export.', 'warning')
        return redirect(url_for('admission_exam.candidates_list', cycle_id=cycle.id))

    safe_cycle = re.sub(r'[^A-Za-z0-9_-]+', '_', cycle.name or 'cycle').strip('_') or 'cycle'
    errors = []

    if action == 'download_admit_cards_pdf':
        pdfs = []
        for c in candidates:
            if not (c.payment_status == 'verified' and c.roll_no):
                errors.append(c.application_id)
                continue
            try:
                pdfs.append(_render_admit_card_pdf(c))
            except Exception as e:
                current_app.logger.exception('Bulk admit PDF failed for %s: %s', c.application_id, e)
                errors.append(c.application_id)
        if not pdfs:
            flash(
                'No admit cards could be generated. Candidates need verified payment and a roll number.',
                'warning',
            )
            return redirect(url_for('admission_exam.candidates_list', cycle_id=cycle.id))
        merged = _merge_pdf_bytes_list(pdfs)
        name = f'admit_cards_{safe_cycle}.pdf'
        if errors:
            flash(f'Skipped {len(errors)} candidate(s) without admit card.', 'warning')
        return send_file(
            io.BytesIO(merged), mimetype='application/pdf',
            as_attachment=True, download_name=name,
        )

    # Application forms (+ attached certificates/transcripts in each PDF)
    # Include every candidate passed in — no payment / roll gate for forms.
    named = []
    for c in candidates:
        try:
            pdf_bytes, engine = _render_application_package_pdf(c)
            named.append((_safe_pdf_filename(c, 'application', engine=engine), pdf_bytes))
        except Exception as e:
            current_app.logger.exception('Bulk application PDF failed for %s: %s', c.application_id, e)
            # Still try a bare form PDF so the candidate is not missing from the ZIP
            try:
                pdf_bytes, engine = _render_application_form_pdf(c)
                named.append((_safe_pdf_filename(c, 'application', engine=engine), pdf_bytes))
                errors.append(f'{c.application_id} (attachments skipped)')
            except Exception:
                current_app.logger.exception('Bare form PDF also failed for %s', c.application_id)
                errors.append(c.application_id)

    if not named:
        flash('Could not generate any application form PDFs.', 'danger')
        return redirect(url_for('admission_exam.candidates_list', cycle_id=cycle.id))

    # Always ZIP for forms export when more than one file, or when ZIP was requested.
    # Multiple candidates → one PDF each inside the archive (verified/unverified/roll irrelevant).
    if action == 'download_forms_zip' or len(named) > 1:
        zbuf = _zip_pdf_bytes(named)
        if errors:
            flash(
                f'Included {len(named)} form(s). {len(errors)} had issues: '
                + ', '.join(str(x) for x in errors[:8])
                + ('…' if len(errors) > 8 else ''),
                'warning',
            )
        return send_file(
            zbuf, mimetype='application/zip',
            as_attachment=True, download_name=f'application_forms_{safe_cycle}.zip',
        )

    if errors:
        flash(f'Some attachments were skipped for: {", ".join(str(x) for x in errors[:8])}', 'warning')
    return send_file(
        io.BytesIO(named[0][1]), mimetype='application/pdf',
        as_attachment=True, download_name=named[0][0],
    )


@admission_exam_bp.route('/cycle/<int:cycle_id>/assign-rolls', methods=['POST'])
@login_required
@cycle_access_required
def assign_rolls(cycle):
    """Sequential rolls for payment-verified candidates who do not yet have one.

    Existing rolls are never renumbered; numbering continues after the highest
    already-assigned roll (or starts at roll_start). Rejected applications are skipped.
    """
    prefix = cycle.roll_prefix or ''
    existing = [
        _roll_numeric_part(c.roll_no, prefix)
        for c in cycle.candidates.filter(
            AdmissionCandidate.roll_no.isnot(None),
            AdmissionCandidate.roll_no != '',
        ).all()
    ]
    existing = [n for n in existing if n is not None]
    next_n = max(existing) + 1 if existing else (cycle.roll_start or 1)

    pending = (
        cycle.candidates
        .filter(
            AdmissionCandidate.payment_status == 'verified',
            AdmissionCandidate.application_status != 'rejected',
            db.or_(
                AdmissionCandidate.roll_no.is_(None),
                AdmissionCandidate.roll_no == '',
            ),
        )
        .order_by(AdmissionCandidate.application_id)
        .all()
    )
    try:
        for c in pending:
            c.roll_no = cycle.format_roll_number(next_n)
            # Mark selected once a roll is issued (admit workflow)
            if c.application_status == 'submitted':
                c.application_status = 'selected'
            next_n += 1
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('assign_rolls failed for cycle %s: %s', cycle.id, e)
        flash(
            'Could not assign roll numbers. Check that the roll_pad_width column exists '
            'in the database, then try again.',
            'danger',
        )
        return redirect(request.referrer or url_for('admission_exam.cycle_detail', cycle_id=cycle.id))

    if pending:
        flash(
            f'Assigned roll numbers to {len(pending)} candidate(s) '
            f'(starting from {cycle.format_roll_number(next_n - len(pending))}).',
            'success',
        )
    else:
        verified = cycle.candidates.filter_by(payment_status='verified').count()
        with_roll = cycle.candidates.filter(
            AdmissionCandidate.roll_no.isnot(None),
            AdmissionCandidate.roll_no != '',
        ).count()
        flash(
            'No new roll numbers assigned. '
            f'Verified payments: {verified}; already have roll: {with_roll}. '
            'Only candidates with verified payment and no roll number are eligible '
            '(rejected applications are skipped).',
            'warning',
        )
    return redirect(request.referrer or url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/unassign-rolls', methods=['POST'])
@login_required
@cycle_access_required
def unassign_rolls(cycle):
    """Clear roll numbers for all candidates in this cycle."""
    rows = (
        cycle.candidates
        .filter(
            AdmissionCandidate.roll_no.isnot(None),
            AdmissionCandidate.roll_no != '',
        )
        .all()
    )
    for c in rows:
        c.roll_no = None
    db.session.commit()
    if rows:
        flash(f'Unassigned roll numbers from {len(rows)} candidate(s).', 'success')
    else:
        flash('No roll numbers to unassign.', 'info')
    return redirect(request.referrer or url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/publish-admit', methods=['POST'])
@login_required
@cycle_access_required
def publish_admit(cycle):
    cycle.admit_published = not cycle.admit_published
    db.session.commit()
    flash('Admit cards published — eligible candidates can now download them.' if cycle.admit_published
          else 'Admit cards unpublished.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/signature', methods=['POST'])
@login_required
@cycle_access_required
def cycle_signature_upload(cycle):
    action = (request.form.get('action') or 'upload').strip()
    if action == 'remove':
        cycle.chairman_signature_path = None
        db.session.commit()
        flash('Chairman signature removed.', 'success')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))

    file_storage = request.files.get('signature')
    if not file_storage or not file_storage.filename:
        flash('Please choose a signature image to upload.', 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    path, err = _save_signature(cycle, file_storage)
    if err:
        flash(err, 'danger')
        return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))
    cycle.chairman_signature_path = path
    db.session.commit()
    flash('Chairman signature uploaded. It will appear on admit cards.', 'success')
    return redirect(url_for('admission_exam.cycle_detail', cycle_id=cycle.id))


@admission_exam_bp.route('/cycle/<int:cycle_id>/signature-image')
@login_required
@cycle_access_required
def cycle_signature_image(cycle):
    path = _signature_abs_path(cycle)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/my-verification-signature', methods=['POST'])
@login_required
def user_verification_signature_upload():
    """Upload/remove the logged-in user's scrutinizer signature (used on application PDFs)."""
    if not user_can_access_admission():
        flash('You do not have access to the Admission Exam module.', 'danger')
        abort(403)
    cycle_id = request.form.get('cycle_id')
    candidate_id = request.form.get('candidate_id')
    if candidate_id and str(candidate_id).isdigit():
        redirect_url = url_for('admission_exam.candidate_detail', candidate_id=int(candidate_id))
    elif cycle_id and str(cycle_id).isdigit():
        redirect_url = url_for('admission_exam.cycle_detail', cycle_id=int(cycle_id))
    else:
        redirect_url = url_for('admission_exam.index')
    action = (request.form.get('action') or 'upload').strip()
    if action == 'remove':
        current_user.signature_path = None
        db.session.commit()
        flash('Your Scrutinizer signature was removed.', 'success')
        return redirect(redirect_url)

    file_storage = request.files.get('signature')
    if not file_storage or not file_storage.filename:
        flash('Please choose a signature image to upload.', 'danger')
        return redirect(redirect_url)
    path, err = _save_user_signature(current_user, file_storage)
    if err:
        flash(err, 'danger')
        return redirect(redirect_url)
    current_user.signature_path = path
    db.session.commit()
    flash(
        'Your signature was saved. It is used on application form PDFs for candidates '
        'you verify, and anywhere else your profile signature is required '
        '(e.g. remuneration). You can also manage it from Profile.',
        'success',
    )
    return redirect(redirect_url)


@admission_exam_bp.route('/my-verification-signature/image')
@login_required
def user_verification_signature_image():
    if not user_can_access_admission():
        abort(403)
    path = _user_signature_abs_path(current_user)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/user/<int:user_id>/scrutinizer-signature')
@login_required
def user_scrutinizer_signature_image(user_id):
    """Serve a committee member's Scrutinizer signature (admission staff only)."""
    if not user_can_access_admission():
        abort(403)
    user = User.query.get_or_404(user_id)
    path = _user_signature_abs_path(user)
    if not path:
        abort(404)
    return send_file(path)


@admission_exam_bp.route('/candidate/<int:candidate_id>/admit-card.pdf')
@login_required
@candidate_access_required
def candidate_admit_card_admin(candidate):
    if not (candidate.payment_status == 'verified' and candidate.roll_no):
        flash('Admit card preview requires verified payment and an assigned roll number.', 'warning')
        return redirect(url_for('admission_exam.candidate_detail', candidate_id=candidate.id))
    if not _photo_abs_path(candidate):
        flash(
            f'Photo file not found on server for {candidate.application_id} '
            f'(stored path: {candidate.photo_path!r}). Admit card will be blank in the photo box. '
            f'Re-upload the photo from candidate edit.',
            'warning',
        )
    try:
        pdf_bytes = _render_admit_card_pdf(candidate)
    except Exception as e:
        current_app.logger.exception('Admin admit card PDF failed for %s: %s', candidate.application_id, e)
        flash('Could not generate admit card PDF. Check server logs for details.', 'danger')
        return redirect(url_for('admission_exam.candidate_detail', candidate_id=candidate.id))
    stamp = datetime.utcnow().strftime('%H%M%S')
    return _admit_pdf_response(
        pdf_bytes,
        f"admit_{candidate.roll_no or candidate.application_id}_{stamp}.pdf",
    )


# --- Candidate account management ------------------------------------------

@admission_exam_bp.route('/candidate/<int:candidate_id>/reset-pin', methods=['POST'])
@login_required
@candidate_access_required
def candidate_reset_pin(candidate):
    pin = _generate_pin()
    candidate.set_pin(pin)
    db.session.commit()
    flash(f'New PIN for {candidate.application_id}: {pin} — share it with the candidate securely; it will not be shown again.', 'success')
    return redirect(url_for('admission_exam.candidate_detail', candidate_id=candidate.id))


@admission_exam_bp.route('/candidate/<int:candidate_id>/edit', methods=['POST'])
@login_required
@candidate_access_required
def candidate_edit(candidate):
    candidate.full_name = (request.form.get('full_name') or candidate.full_name).strip().upper()
    candidate.phone = (request.form.get('phone') or candidate.phone).strip()
    candidate.email = (request.form.get('email') or '').strip() or None
    candidate.extra_fields = json.dumps(
        _collect_extra_fields(
            request.form,
            cycle=candidate.cycle,
            existing=_parse_extra_fields(candidate),
        ),
        ensure_ascii=False,
    )
    photo = request.files.get('photo')
    if photo and photo.filename:
        photo_path, photo_err = _save_photo(candidate.cycle, candidate.application_id, photo)
        if photo_err:
            flash(photo_err, 'danger')
            return redirect(url_for('admission_exam.candidate_detail', candidate_id=candidate.id))
        candidate.photo_path = photo_path
    signature = request.files.get('candidate_signature')
    if signature and signature.filename:
        sig_path, sig_err = _save_candidate_signature(
            candidate.cycle, candidate.application_id, signature
        )
        if sig_err:
            flash(sig_err, 'danger')
            return redirect(url_for('admission_exam.candidate_detail', candidate_id=candidate.id))
        candidate.signature_path = sig_path
    db.session.commit()
    flash('Candidate information updated.', 'success')
    return redirect(url_for('admission_exam.candidate_detail', candidate_id=candidate.id))


@admission_exam_bp.route('/candidate/<int:candidate_id>/delete', methods=['POST'])
@login_required
@candidate_access_required
def candidate_delete(candidate):
    cycle_id = candidate.cycle_id
    db.session.delete(candidate)
    db.session.commit()
    flash('Candidate application deleted.', 'success')
    return redirect(url_for('admission_exam.candidates_list', cycle_id=cycle_id))


# --- Export ----------------------------------------------------------------

@admission_exam_bp.route('/cycle/<int:cycle_id>/export.xlsx')
@login_required
@cycle_access_required
def export_candidates(cycle):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = 'Candidates'
    extras = extra_field_defs(cycle)
    headers = [
        'Application ID', 'Roll No', 'Full Name', 'Phone', 'Email',
        'Payment Method', 'MFS TxnID', 'MFS Sender Account',
        'Bank Slip / Txn No', 'Bank Slip Uploaded',
        'Payment Status', 'Payment Note', 'Application Status', 'Applied At',
    ]
    headers += [label for _key, label in extras]
    ws.append(headers)
    for c in cycle.candidates.order_by(AdmissionCandidate.application_id).all():
        extra = _parse_extra_fields(c)
        method = (getattr(c, 'payment_method', None) or DEFAULT_PAYMENT_METHOD).strip().lower()
        row = [
            c.application_id, c.roll_no or '', c.full_name, c.phone, c.email or '',
            PAYMENT_METHOD_LABELS.get(method, method),
            c.rocket_txn_id or '', c.rocket_sender_phone or '',
            getattr(c, 'bank_slip_txn_no', None) or '',
            'Yes' if getattr(c, 'bank_slip_path', None) else '',
            c.payment_status, c.payment_note or '', c.application_status,
            format_bd(c.created_at, '%Y-%m-%d %H:%M', default=''),
        ]
        row += [extra.get(key, '') for key, _label in extras]
        ws.append(row)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    safe_name = re.sub(r'[^A-Za-z0-9_-]+', '_', cycle.name).strip('_') or 'cycle'
    return send_file(buffer,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'candidates_{safe_name}.xlsx')


@admission_exam_bp.route('/cycle/<int:cycle_id>/application-forms.pdf')
@login_required
@cycle_access_required
def export_application_forms_pdf(cycle):
    """All candidates' forms + attachments (ignores list filters). ZIP if more than one."""
    candidates = _all_cycle_candidates(cycle)
    return _bulk_download_candidates_pdfs(cycle, candidates, 'download_forms_pdf')


@admission_exam_bp.route('/cycle/<int:cycle_id>/application-forms.zip')
@login_required
@cycle_access_required
def export_application_forms_zip(cycle):
    """ZIP of every candidate's form + attachments — no payment/roll/status filter."""
    candidates = _all_cycle_candidates(cycle)
    return _bulk_download_candidates_pdfs(cycle, candidates, 'download_forms_zip')


@admission_exam_bp.route('/cycle/<int:cycle_id>/admit-cards.pdf')
@login_required
@cycle_access_required
def export_admit_cards_pdf(cycle):
    """Merged admit cards for filtered candidates who have verified payment + roll."""
    candidates, _payment, _status, _search = _filter_cycle_candidates(cycle)
    return _bulk_download_candidates_pdfs(cycle, candidates, 'download_admit_cards_pdf')

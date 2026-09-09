"""Unified upload validation (FILE-03 / FILE-04 / FILE-05).

Per-purpose extension allowlists, magic-byte sniffing (no libmagic),
Pillow re-encode for images, PDF header (+ optional page limit),
and safe download response headers.
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Iterable

from werkzeug.utils import secure_filename

# Decompression / pixel bombs
try:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = 40_000_000
except Exception:  # pragma: no cover
    Image = None  # type: ignore


class UploadError(Exception):
    """User-facing validation failure."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class UploadPurpose:
    name: str
    extensions: frozenset[str]
    max_bytes: int
    max_label: str
    # Kinds returned by sniff_kind(); empty means skip magic (text only).
    magic_kinds: frozenset[str]
    reencode_image: bool = False
    max_image_dims: tuple[int, int] | None = None
    max_pdf_pages: int | None = None


# --- Purpose profiles ---------------------------------------------------------

QA_PURPOSE = UploadPurpose(
    name='qa',
    extensions=frozenset({'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'txt', 'doc', 'docx'}),
    max_bytes=10 * 1024 * 1024,
    max_label='10 MB',
    magic_kinds=frozenset({
        'pdf', 'png', 'jpg', 'gif', 'webp', 'txt', 'doc', 'docx',
    }),
    reencode_image=False,
    max_pdf_pages=100,
)

LANDING_PURPOSE = UploadPurpose(
    name='landing',
    # FILE-05: no zip/rar/exe — public download surface
    extensions=frozenset({
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'png', 'jpg', 'jpeg', 'gif', 'webp', 'txt',
    }),
    max_bytes=10 * 1024 * 1024,
    max_label='10 MB',
    magic_kinds=frozenset({
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'png', 'jpg', 'gif', 'webp', 'txt',
    }),
    max_pdf_pages=200,
)

DOCUMENT_IMAGE_PURPOSE = UploadPurpose(
    name='document_image',
    extensions=frozenset({'png', 'jpg', 'jpeg'}),
    max_bytes=5 * 1024 * 1024,
    max_label='5 MB',
    magic_kinds=frozenset({'png', 'jpg'}),
    reencode_image=True,
    max_image_dims=(2400, 3200),
)

PROFILE_IMAGE_PURPOSE = UploadPurpose(
    name='profile_image',
    extensions=frozenset({'png', 'jpg', 'jpeg', 'gif', 'webp'}),
    max_bytes=16 * 1024 * 1024,
    max_label='16 MB',
    magic_kinds=frozenset({'png', 'jpg', 'gif', 'webp'}),
    reencode_image=True,
    max_image_dims=(2000, 2000),
)


PURPOSES = {
    QA_PURPOSE.name: QA_PURPOSE,
    LANDING_PURPOSE.name: LANDING_PURPOSE,
    DOCUMENT_IMAGE_PURPOSE.name: DOCUMENT_IMAGE_PURPOSE,
    PROFILE_IMAGE_PURPOSE.name: PROFILE_IMAGE_PURPOSE,
}


# --- Magic sniffing -----------------------------------------------------------

_JPEG = b'\xff\xd8\xff'
_PNG = b'\x89PNG\r\n\x1a\n'
_GIF87 = b'GIF87a'
_GIF89 = b'GIF89a'
_WEBP_RIFF = b'RIFF'
_PDF = b'%PDF-'
_OLE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
_ZIP = b'PK\x03\x04'


def _office_kind_from_ooxml(data: bytes) -> str | None:
    """Distinguish docx/xlsx/pptx from generic zip."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = {n.replace('\\', '/') for n in zf.namelist()}
    except zipfile.BadZipFile:
        return None
    if '[Content_Types].xml' not in names and not any(
        n.startswith('word/') or n.startswith('xl/') or n.startswith('ppt/') for n in names
    ):
        return None
    if any(n.startswith('word/') for n in names):
        return 'docx'
    if any(n.startswith('xl/') for n in names):
        return 'xlsx'
    if any(n.startswith('ppt/') for n in names):
        return 'pptx'
    # Content_Types present but unknown — treat as generic ooxml (reject unless ext maps)
    return 'ooxml'


def _looks_like_text(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:8192]
    if b'\x00' in sample:
        return False
    # Allow UTF-8 BOM
    if sample.startswith(b'\xef\xbb\xbf'):
        sample = sample[3:]
    try:
        text = sample.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = sample.decode('latin-1')
        except UnicodeDecodeError:
            return False
    if not text.strip():
        return False
    # Reject if mostly control chars (except common whitespace)
    bad = sum(1 for ch in text if ord(ch) < 32 and ch not in '\t\r\n')
    return (bad / max(len(text), 1)) < 0.05


def sniff_kind(data: bytes) -> str | None:
    """Return a normalized kind string, or None if unknown."""
    if not data:
        return None
    if data.startswith(_JPEG):
        return 'jpg'
    if data.startswith(_PNG):
        return 'png'
    if data.startswith(_GIF87) or data.startswith(_GIF89):
        return 'gif'
    if data.startswith(_WEBP_RIFF) and len(data) >= 12 and data[8:12] == b'WEBP':
        return 'webp'
    if data.startswith(_PDF):
        return 'pdf'
    if data.startswith(_OLE):
        # Ambiguous among doc/xls/ppt — callers match via extension family
        return 'ole'
    if data.startswith(_ZIP):
        ooxml = _office_kind_from_ooxml(data)
        if ooxml:
            return ooxml
        return 'zip'
    if _looks_like_text(data):
        return 'txt'
    return None


def _ext_of(filename: str) -> str:
    name = secure_filename(filename or '') or ''
    if '.' not in name:
        return ''
    return name.rsplit('.', 1)[-1].lower()


def _normalize_ext(ext: str) -> str:
    ext = (ext or '').lower().lstrip('.')
    if ext == 'jpeg':
        return 'jpg'
    return ext


def _magic_matches_ext(kind: str | None, ext: str) -> bool:
    """Whether sniffed kind is compatible with declared extension."""
    if not kind:
        return False
    ext = _normalize_ext(ext)
    if kind == 'jpg' and ext in ('jpg', 'jpeg'):
        return True
    if kind == ext:
        return True
    if kind == 'ole' and ext in ('doc', 'xls', 'ppt'):
        return True
    if kind == 'ooxml' and ext in ('docx', 'xlsx', 'pptx'):
        return True
    # Map ooxml specific kinds
    if kind in ('docx', 'xlsx', 'pptx') and ext == kind:
        return True
    return False


def read_upload_bytes(file_storage, max_bytes: int) -> bytes:
    """Read entire upload into memory with a hard size cap."""
    if file_storage is None:
        raise UploadError('No file uploaded.')
    stream = getattr(file_storage, 'stream', None) or file_storage
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)
    except Exception:
        size = None
    if size is not None and size <= 0:
        raise UploadError('File is empty.')
    if size is not None and size > max_bytes:
        raise UploadError(
            f'File is too large ({size / (1024 * 1024):.1f} MB). '
            f'Maximum allowed size is {max_bytes / (1024 * 1024):.0f} MB.'
        )
    data = stream.read(max_bytes + 1)
    try:
        stream.seek(0)
    except Exception:
        pass
    if not data:
        raise UploadError('File is empty.')
    if len(data) > max_bytes:
        raise UploadError(
            f'File is too large. Maximum allowed size is {max_bytes / (1024 * 1024):.0f} MB.'
        )
    return data


def count_pdf_pages(data: bytes) -> int | None:
    """Best-effort page count; None if library unavailable or parse fails."""
    if not data.startswith(_PDF):
        return None
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:
        # Fallback: crude /Type /Page count (over-counts on some files; only upper-bound check)
        try:
            return len(re.findall(rb'/Type\s*/Page(?![s])', data))
        except Exception:
            return None


def assert_pdf_ok(data: bytes, max_pages: int | None = None) -> None:
    if not data.startswith(_PDF):
        raise UploadError('File is not a valid PDF.')
    if max_pages is None:
        return
    pages = count_pdf_pages(data)
    if pages is not None and pages > max_pages:
        raise UploadError(f'PDF has too many pages ({pages}). Maximum is {max_pages}.')


def reencode_image(
    data: bytes,
    *,
    max_dims: tuple[int, int] | None = None,
    prefer_png: bool = False,
) -> tuple[bytes, str]:
    """Decode with Pillow and re-encode; returns (bytes, ext)."""
    if Image is None:
        raise UploadError('Image processing is unavailable on this server.')
    try:
        img = Image.open(io.BytesIO(data))
        try:
            from PIL import ImageOps

            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        keep_alpha = prefer_png or img.mode in ('RGBA', 'LA') or (
            img.mode == 'P' and 'transparency' in img.info
        )
        if keep_alpha:
            img = img.convert('RGBA')
            out_ext = 'png'
        else:
            img = img.convert('RGB')
            out_ext = 'jpg'
        if max_dims:
            resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.LANCZOS)
            img.thumbnail(max_dims, resample)
        buf = io.BytesIO()
        if out_ext == 'png':
            img.save(buf, format='PNG', optimize=True)
        else:
            img.save(buf, format='JPEG', quality=85, optimize=True)
        return buf.getvalue(), out_ext
    except UploadError:
        raise
    except Exception:
        raise UploadError('Could not read the image. Please upload a valid JPG or PNG.')


@dataclass
class ValidatedUpload:
    original_name: str
    ext: str
    data: bytes
    kind: str | None
    purpose: UploadPurpose


def validate_upload(file_storage, purpose: UploadPurpose | str) -> ValidatedUpload:
    """Validate extension + magic (+ PDF rules). Does not write to disk."""
    if isinstance(purpose, str):
        purpose = PURPOSES[purpose]
    filename = secure_filename(getattr(file_storage, 'filename', None) or '') or ''
    if not filename or '.' not in filename:
        raise UploadError('Invalid file name.')
    ext = _normalize_ext(_ext_of(filename))
    # Keep jpeg as jpeg in original message checks — allowlist uses jpg/jpeg
    raw_ext = filename.rsplit('.', 1)[-1].lower()
    if raw_ext not in purpose.extensions and ext not in purpose.extensions:
        allowed = ', '.join(sorted(purpose.extensions))
        raise UploadError(f'File type not allowed. Allowed: {allowed}.')

    data = read_upload_bytes(file_storage, purpose.max_bytes)
    kind = sniff_kind(data)

    if purpose.magic_kinds:
        # Text: allow without strong magic if declared txt and looks like text
        if ext == 'txt':
            if kind != 'txt':
                raise UploadError('Text file content is invalid.')
        elif not _magic_matches_ext(kind, raw_ext if raw_ext != 'jpeg' else 'jpg'):
            raise UploadError(
                'File content does not match its extension. '
                'Please upload a genuine file of the allowed type.'
            )
        # Reject plain zip when purpose does not allow zip
        if kind == 'zip' and 'zip' not in purpose.extensions:
            raise UploadError('Archive files (ZIP) are not allowed.')

    if kind == 'pdf' or ext == 'pdf':
        assert_pdf_ok(data, purpose.max_pdf_pages)

    return ValidatedUpload(
        original_name=filename[:255],
        ext=ext if ext != 'jpeg' else 'jpg',
        data=data,
        kind=kind,
        purpose=purpose,
    )


def materialize_validated(
    validated: ValidatedUpload,
    dest_path: str,
    *,
    force_reencode: bool | None = None,
) -> str:
    """Write validated bytes to dest_path; returns final extension used."""
    purpose = validated.purpose
    data = validated.data
    ext = validated.ext
    do_reencode = purpose.reencode_image if force_reencode is None else force_reencode
    if do_reencode and ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        prefer_png = ext == 'png' or (validated.kind in ('png', 'gif', 'webp'))
        data, ext = reencode_image(
            data,
            max_dims=purpose.max_image_dims,
            prefer_png=prefer_png and ext != 'jpg',
        )
        # Profile may keep jpeg for photos
        if validated.purpose.name == 'profile_image' and ext == 'png' and validated.ext in ('jpg', 'jpeg'):
            # already handled by prefer_png
            pass
    os.makedirs(os.path.dirname(dest_path) or '.', exist_ok=True)
    # If reencode changed ext, caller should pass dest with correct ext; rewrite if needed
    base, cur_ext = os.path.splitext(dest_path)
    if cur_ext.lstrip('.').lower() != ext:
        dest_path = f'{base}.{ext}'
    with open(dest_path, 'wb') as fh:
        fh.write(data)
    return ext


def validate_and_save(
    file_storage,
    purpose: UploadPurpose | str,
    dest_path: str,
) -> tuple[str, str]:
    """Validate + write. Returns (final_abs_path, original_filename)."""
    validated = validate_upload(file_storage, purpose)
    ext = materialize_validated(validated, dest_path)
    base, _ = os.path.splitext(dest_path)
    final_path = f'{base}.{ext}'
    if final_path != dest_path and os.path.isfile(dest_path) and not os.path.isfile(final_path):
        os.replace(dest_path, final_path)
    return final_path, validated.original_name


def apply_download_headers(response, *, as_attachment: bool = True):
    """Force attachment semantics + nosniff on a Flask response."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    if as_attachment:
        # Ensure browsers treat as download when Content-Disposition missing
        cd = response.headers.get('Content-Disposition', '')
        if cd and 'attachment' not in cd.lower():
            response.headers['Content-Disposition'] = cd.replace('inline', 'attachment')
        elif not cd:
            response.headers['Content-Disposition'] = 'attachment'
    return response


def allowed_extensions_accept_attr(extensions: Iterable[str]) -> str:
    """Build an HTML accept= attribute value."""
    parts = []
    for ext in sorted(set(extensions)):
        parts.append(f'.{ext}')
    return ','.join(parts)

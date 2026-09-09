"""Email address and HTTP download-header safety (INJ-05 / INJ-06)."""
from __future__ import annotations

from email.utils import formataddr
from urllib.parse import quote

from werkzeug.utils import secure_filename

try:
    from email_validator import EmailNotValidError, validate_email
except ImportError:  # pragma: no cover
    EmailNotValidError = Exception  # type: ignore
    validate_email = None  # type: ignore


class EmailSafetyError(ValueError):
    """User-facing email validation failure."""


def contains_header_injection(value: str | None) -> bool:
    if value is None:
        return False
    return any(ch in str(value) for ch in ('\r', '\n', '\0'))


def sanitize_header_text(value: str | None, *, max_len: int = 200) -> str:
    """Strip CR/LF/NUL from free-text header values (Subject, display names)."""
    text = '' if value is None else str(value)
    for ch in ('\r', '\n', '\0'):
        text = text.replace(ch, ' ')
    text = ' '.join(text.split())
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def normalize_email(value: str | None, *, check_deliverability: bool = False) -> str:
    """Validate and normalize an email; reject header-injection attempts."""
    if value is None:
        raise EmailSafetyError('Email is required.')
    raw = str(value).strip()
    if not raw:
        raise EmailSafetyError('Email is required.')
    if contains_header_injection(raw):
        raise EmailSafetyError('Invalid email address.')
    if validate_email is None:
        # Minimal fallback if package missing on a host
        if '@' not in raw or raw.count('@') != 1:
            raise EmailSafetyError('Invalid email address.')
        local, _, domain = raw.partition('@')
        if not local or not domain or '.' not in domain:
            raise EmailSafetyError('Invalid email address.')
        return raw.lower()
    try:
        result = validate_email(raw, check_deliverability=check_deliverability)
    except EmailNotValidError as exc:
        raise EmailSafetyError('Invalid email address.') from exc
    normalized = (result.normalized or raw).strip()
    if contains_header_injection(normalized):
        raise EmailSafetyError('Invalid email address.')
    return normalized


def format_to_header(recipient: str) -> str:
    """Safe ``To`` header value (validated address only)."""
    addr = normalize_email(recipient)
    # formataddr quotes/encodes display names; empty name → bare addr
    return formataddr(('', addr))


def format_from_header(sender: str, display_name: str | None = None) -> str:
    """Safe ``From`` header: validated address + sanitized display name."""
    addr = normalize_email(sender)
    name = sanitize_header_text(display_name, max_len=80) if display_name else ''
    return formataddr((name, addr))


def safe_download_filename(filename: str | None, *, default: str = 'download') -> str:
    """ASCII-safe basename for Content-Disposition ``filename=``."""
    raw = '' if filename is None else str(filename)
    for ch in ('\r', '\n', '\0'):
        raw = raw.replace(ch, '')
    raw = raw.strip().replace('\\', '/').split('/')[-1]
    cleaned = secure_filename(raw) or ''
    if not cleaned:
        cleaned = secure_filename(default) or 'download'
    # Avoid empty extension-only oddities
    if cleaned in ('.', '..'):
        cleaned = 'download'
    return cleaned[:180]


def content_disposition_attachment(filename: str | None, *, default: str = 'download') -> str:
    """Build ``Content-Disposition: attachment`` with RFC 5987 ``filename*``."""
    raw = '' if filename is None else str(filename)
    for ch in ('\r', '\n', '\0'):
        raw = raw.replace(ch, '')
    raw = raw.strip().replace('\\', '/').split('/')[-1] or default
    ascii_name = safe_download_filename(raw, default=default)
    # UTF-8 filename* for original (CRLF-stripped) name when it differs
    star = quote(raw, safe='')
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{star}"

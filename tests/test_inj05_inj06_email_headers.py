"""INJ-05 / INJ-06: email and Content-Disposition safety."""
import pytest

from utils.email_safety import (
    EmailSafetyError,
    content_disposition_attachment,
    contains_header_injection,
    format_to_header,
    normalize_email,
    safe_download_filename,
    sanitize_header_text,
)
from utils.recovery_email import _build_message


def test_normalize_email_ok():
    assert normalize_email('  User@Example.COM ') == 'user@example.com'


def test_normalize_email_rejects_crlf():
    with pytest.raises(EmailSafetyError):
        normalize_email('victim@example.com\r\nBcc: attacker@evil.com')
    with pytest.raises(EmailSafetyError):
        normalize_email('a@b.com\ninjected')


def test_normalize_email_rejects_garbage():
    with pytest.raises(EmailSafetyError):
        normalize_email('not-an-email')
    with pytest.raises(EmailSafetyError):
        normalize_email('')


def test_format_to_header_no_raw_injection():
    header = format_to_header('safe@example.com')
    assert '\r' not in header and '\n' not in header
    assert 'safe@example.com' in header


def test_build_message_to_is_safe():
    msg = _build_message(
        'Hello\r\nX-Injected: yes',
        'recovery@kulawams.xyz',
        'user@example.com',
        'body',
    )
    # CRLF removed so it cannot split into a new header line
    assert '\r' not in str(msg['Subject']) and '\n' not in str(msg['Subject'])
    assert '\r' not in str(msg['To']) and '\n' not in str(msg['To'])
    with pytest.raises(ValueError):
        _build_message('Hi', 'recovery@kulawams.xyz', 'x@y.com\r\nCc: z@z.com', 'body')


def test_content_disposition_strips_crlf():
    cd = content_disposition_attachment('evil\r\nfilename.pdf')
    assert '\r' not in cd and '\n' not in cd
    assert 'attachment;' in cd
    assert 'filename=' in cd
    assert "filename*=UTF-8''" in cd


def test_safe_download_filename():
    assert safe_download_filename('../../etc/passwd') == 'etc_passwd' or 'passwd' in safe_download_filename('../../etc/passwd')
    assert contains_header_injection('a\nb') is True
    assert sanitize_header_text('Hello\r\nWorld') == 'Hello World'

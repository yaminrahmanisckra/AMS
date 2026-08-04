"""
Send password-recovery emails via MAIL_* only (recovery@kulawams.xyz).

Uses smtplib directly for cPanel SMTP. Short timeouts so the forgot-password
page does not hang. Does NOT use Flask-Mail (no connect timeout → can hang).

Does not fall back to noreply@ — keep recovery and notification channels separate.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from contextlib import contextmanager
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from flask import current_app

# Keep forgot-password responsive on bad SMTP configs
SMTP_TIMEOUT_SEC = 15


def _sync_mail_from_os_environ():
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        return
    mail_keys = (
        'MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USE_SSL',
        'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_DEFAULT_SENDER', 'MAIL_FROM_NAME',
    )
    for k in mail_keys:
        v = os.environ.get(k)
        if v is None or str(v).strip() == '':
            continue
        if k.endswith('_PASSWORD'):
            app.config[k] = str(v).rstrip('\r\n')
        else:
            app.config[k] = str(v).strip()


def _mail_setting(key: str, default=None):
    v = os.environ.get(key)
    if v is not None and str(v).strip() != '':
        return v
    v = current_app.config.get(key)
    if v is not None and v != '':
        return v
    return default


def _mail_bool(key: str, fallback=False) -> bool:
    raw = _mail_setting(key, fallback)
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _ssl_context():
    """
    SSL context for SMTP.

    Many cPanel/shared hosts intercept outbound TLS and cause
    CERTIFICATE_VERIFY_FAILED / hostname mismatch.
    Set MAIL_SSL_VERIFY=True only when the host has a working CA bundle.
    Default: verify off on CPANEL, otherwise on.
    """
    cpanel = str(os.environ.get('CPANEL') or os.environ.get('cPanel') or '').strip() in (
        '1', 'true', 'yes', 'on',
    )
    verify_default = not cpanel
    verify = _mail_bool('MAIL_SSL_VERIFY', verify_default)
    if verify:
        return ssl.create_default_context()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _format_from(sender: str, display_name: str | None = None) -> str:
    name = (display_name or '').strip()
    addr = (sender or '').strip()
    if name and addr:
        return formataddr((name, addr))
    return addr


def _build_message(
    subject: str,
    sender: str,
    recipient: str,
    text_body: str,
    html_body: str | None = None,
    from_name: str | None = None,
):
    from email.utils import formatdate, make_msgid

    if html_body:
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(text_body or '', 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    else:
        msg = MIMEText(text_body or '', 'plain', 'utf-8')

    from_header = _format_from(sender, from_name)
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = from_header
    msg['To'] = recipient
    msg['Date'] = formatdate(localtime=True)
    # Do NOT set Auto-Submitted — Hosting Bangladesh outbound filter often
    # treats auto-generated headers as bulk/spam (550 classified as SPAM).
    domain = 'localhost'
    if '@' in sender:
        domain = sender.rsplit('@', 1)[-1].strip('>')
    msg['Message-ID'] = make_msgid(domain=domain)
    return msg


def _normalize_mail_password(password):
    """Strip whitespace/quotes; Gmail App Passwords are often copied with spaces."""
    if password is None:
        return password
    if not isinstance(password, str):
        return password
    pw = password.rstrip('\r\n').strip()
    if len(pw) >= 2 and pw[0] == pw[-1] and pw[0] in ('"', "'"):
        pw = pw[1:-1].strip()
    for ch in ('\ufeff', '\u200b', '\u200c', '\u200d', '\u00a0'):
        pw = pw.replace(ch, '')
    if ' ' in pw and len(pw.replace(' ', '')) >= 16:
        pw = pw.replace(' ', '')
    return pw


def _smtp_auth_diag(user: str, password, host: str | None = None) -> str:
    """Safe hint for logs — never includes the secret."""
    u = (user or '').strip()
    pw = _normalize_mail_password(password) or ''
    host_l = (host or '').strip().lower()
    hints = [f'user={u or "(empty)"}', f'pw_len={len(pw)}']
    if 'brevo' not in host_l and 'sendinblue' not in host_l:
        return '; '.join(hints)
    low = pw.lower()
    if low.startswith('xkeysib-'):
        hints.append('WRONG_KEY_TYPE: API key (xkeysib). Use an SMTP key from SMTP & API → SMTP')
    elif len(pw) > 80 or low.startswith('xsmtpsib-'):
        hints.append('LIKELY_WRONG_KEY: Brevo SMTP key is normally 64 chars (or short 15)')
    elif len(pw) in (15, 64):
        hints.append('pw_len_matches_brevo_smtp_key_size')
    if u and not u.lower().endswith('@smtp-brevo.com'):
        hints.append('Brevo SMTP login usually ends with @smtp-brevo.com')
    return '; '.join(hints)


def _normalize_smtp_security(host, port, use_tls, use_ssl):
    """
    Avoid SSL/TLS on plain local submission (WRONG_VERSION_NUMBER on :25).
    Force expected security for 465 / 587.
    """
    host = (host or 'localhost').strip()
    port = int(port or 25)
    use_tls = bool(use_tls)
    use_ssl = bool(use_ssl)
    host_l = host.lower()
    if port == 25 or host_l in ('localhost', '127.0.0.1', '::1'):
        return host, port, False, False
    if port == 465:
        return host, port, False, True
    if port == 587:
        return host, port, True, False
    return host, port, use_tls, use_ssl


def _endpoint_candidates(host, port, use_tls, use_ssl, sender_email: str):
    """
    Primary endpoint first; then Hosting Bangladesh / cPanel submission alternatives.
    Prefer server.hostingbangladesh.com:465 (SSL) as recommended by the host.
    """
    primary = _normalize_smtp_security(host, port, use_tls, use_ssl)
    out = [primary]
    domain = ''
    if sender_email and '@' in sender_email:
        domain = sender_email.rsplit('@', 1)[-1].strip().lower()

    preferred = [
        ('server.hostingbangladesh.com', 465, False, True),
        ('server.hostingbangladesh.com', 587, True, False),
    ]
    if domain:
        preferred.extend([
            (f'mail.{domain}', 465, False, True),
            (f'mail.{domain}', 587, True, False),
            (domain, 465, False, True),
            (domain, 587, True, False),
            ('localhost', 25, False, False),
        ])
    for alt in preferred:
        if alt not in out:
            out.append(alt)
    return out


def _is_spam_reject(exc: BaseException) -> bool:
    text = str(exc).lower()
    return 'classified as spam' in text or ('550' in text and 'spam' in text)


def _find_sendmail_binary() -> str | None:
    """cPanel/Exim local injection path (often same as webmail)."""
    import shutil
    for candidate in (
        os.environ.get('MAIL_SENDMAIL_PATH') or '',
        '/usr/sbin/sendmail',
        '/usr/lib/sendmail',
        shutil.which('sendmail') or '',
    ):
        path = (candidate or '').strip()
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _send_via_sendmail(raw: bytes, envelope_from: str, recipient: str) -> str:
    """
    Pipe a full RFC822 message to sendmail/exim.
    Some hosts reject SMTP submission as spam but still accept local sendmail.
    """
    import subprocess

    binary = _find_sendmail_binary()
    if not binary:
        raise RuntimeError('sendmail binary not found')
    # -i : do not treat lone '.' as end of message
    # -f : envelope sender (must be a local mailbox the account may use)
    cmd = [binary, '-i', '-f', envelope_from, '--', recipient]
    proc = subprocess.run(
        cmd,
        input=raw,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b'').decode('utf-8', errors='replace').strip()
        raise RuntimeError(f'sendmail exit {proc.returncode}: {err or "unknown error"}')
    return f'sendmail:{binary}'


@contextmanager
def _smtp_session(host, port, user, password, use_tls, use_ssl, timeout=SMTP_TIMEOUT_SEC):
    host, port, use_tls, use_ssl = _normalize_smtp_security(host, port, use_tls, use_ssl)
    user = (user or '').strip()
    password = _normalize_mail_password(password)

    context = _ssl_context()
    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
    try:
        try:
            server.ehlo()
        except Exception:
            pass
        if use_tls and not use_ssl:
            server.starttls(context=context)
            try:
                server.ehlo()
            except Exception:
                pass
        if user and password:
            try:
                server.login(user, password)
            except smtplib.SMTPAuthenticationError:
                current_app.logger.error(
                    'SMTP AUTH failed: %s', _smtp_auth_diag(user, password, host)
                )
                raise
        yield server
    finally:
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass


def _envelope_sender(from_header: str, fallback: str) -> str:
    """Extract bare address for SMTP MAIL FROM."""
    addr = (fallback or '').strip()
    raw = (from_header or '').strip()
    if '<' in raw and '>' in raw:
        addr = raw.rsplit('<', 1)[-1].rstrip('>').strip() or addr
    return addr


def send_smtp_message(
    *,
    host,
    port,
    use_tls,
    use_ssl,
    user,
    password,
    sender,
    recipient,
    subject,
    text_body,
    html_body=None,
    from_name=None,
    timeout=SMTP_TIMEOUT_SEC,
    try_cpanel_alternatives=True,
) -> str:
    """
    Send one message. Returns the endpoint string that succeeded (host:port or sendmail:…).
    Retries mail.domain submission if localhost is rejected as spam, then local sendmail.
    """
    recipient = (recipient or '').strip()
    sender = (sender or '').strip()
    user = (user or '').strip()
    if not recipient:
        raise RuntimeError('Missing recipient email')
    if not sender:
        raise RuntimeError('Missing sender email')

    msg = _build_message(subject, sender, recipient, text_body or '', html_body, from_name=from_name)
    msg['Reply-To'] = sender
    envelope_from = _envelope_sender(msg['From'], sender)
    raw = msg.as_bytes()

    if try_cpanel_alternatives:
        candidates = _endpoint_candidates(host, port, use_tls, use_ssl, sender)
    else:
        candidates = [_normalize_smtp_security(host, port, use_tls, use_ssl)]

    errors = []
    spam_hits = 0
    for h, p, tls, ssl_on in candidates:
        endpoint = f'{h}:{p}'
        try:
            with _smtp_session(
                host=h,
                port=p,
                user=user or sender,
                password=password,
                use_tls=tls,
                use_ssl=ssl_on,
                timeout=timeout,
            ) as smtp:
                smtp.sendmail(envelope_from, [recipient], raw)
            if endpoint != f'{str(host).strip()}:{int(port or 25)}':
                current_app.logger.info('SMTP delivered via alternate endpoint %s', endpoint)
            return endpoint
        except Exception as err:
            errors.append(f'{endpoint}: {err}')
            current_app.logger.warning('SMTP attempt failed (%s): %s', endpoint, err)
            if _is_spam_reject(err):
                spam_hits += 1
            continue

    # Last resort on cPanel: local sendmail (same path webmail often uses)
    allow_sendmail = _mail_bool('MAIL_USE_SENDMAIL', True)
    if allow_sendmail and (spam_hits or errors):
        try:
            endpoint = _send_via_sendmail(raw, envelope_from, recipient)
            current_app.logger.info('Mail delivered via %s', endpoint)
            return endpoint
        except Exception as sm_err:
            errors.append(f'sendmail: {sm_err}')
            current_app.logger.warning('sendmail fallback failed: %s', sm_err)

    raise RuntimeError(' | '.join(errors) if errors else 'Email send failed')


def send_recovery_email(subject: str, recipient: str, text_body: str, html_body: str | None = None) -> None:
    """
    Send one password-reset email via MAIL_* only (recovery@).

    MAIL_USERNAME / MAIL_DEFAULT_SENDER should both be recovery@kulawams.xyz
    on cPanel localhost (login and From must match the mailbox).
    """
    _sync_mail_from_os_environ()
    recipient = (recipient or '').strip()
    if not recipient:
        raise RuntimeError('Missing recipient email')

    mail_user = (_mail_setting('MAIL_USERNAME') or '').strip()
    # Hosting Bangladesh: SMTP login and From must be the identical mailbox address
    sender = mail_user or (_mail_setting('MAIL_DEFAULT_SENDER') or '').strip()
    default_sender = (_mail_setting('MAIL_DEFAULT_SENDER') or '').strip()
    if default_sender and mail_user and default_sender.lower() != mail_user.lower():
        current_app.logger.warning(
            'MAIL_DEFAULT_SENDER (%s) differs from MAIL_USERNAME (%s); '
            'using MAIL_USERNAME as From per host requirement',
            default_sender,
            mail_user,
        )
    if not sender or not mail_user:
        raise RuntimeError(
            'MAIL_USERNAME / MAIL_DEFAULT_SENDER not set. '
            'Use recovery@kulawams.xyz for password recovery.'
        )

    # Bare From (no display name) — matches SMTP login exactly unless overridden
    from_name = (_mail_setting('MAIL_FROM_NAME') or '').strip() or None
    try:
        send_smtp_message(
            host=_mail_setting('MAIL_SERVER') or 'localhost',
            port=_mail_setting('MAIL_PORT') or 25,
            use_tls=_mail_bool('MAIL_USE_TLS', False),
            use_ssl=_mail_bool('MAIL_USE_SSL', False),
            user=mail_user,
            password=_mail_setting('MAIL_PASSWORD'),
            sender=mail_user,
            recipient=recipient,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            from_name=from_name,
            try_cpanel_alternatives=True,
        )
    except Exception as smtp_err:
        diag = _smtp_auth_diag(mail_user, _mail_setting('MAIL_PASSWORD'), _mail_setting('MAIL_SERVER'))
        hint = ''
        if _is_spam_reject(smtp_err):
            hint = (
                ' | Host outbound content filter rejected the message. '
                'Use SMTP host server.hostingbangladesh.com port 465 (SSL), '
                'keep MAIL_USERNAME and MAIL_DEFAULT_SENDER identical, '
                'and ensure the message body is specific (name, account, link purpose, validity).'
            )
        raise RuntimeError(
            f'MAIL_* ({_mail_setting("MAIL_SERVER")}:{_mail_setting("MAIL_PORT")}): '
            f'{smtp_err} [{diag}]{hint}'
        ) from smtp_err

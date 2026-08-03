"""
Send password-recovery emails via MAIL_* (e.g. recovery@).

Uses smtplib directly for cPanel SMTP. Short timeouts so the forgot-password
page does not hang. Falls back once to NOTIFICATION_MAIL_* (noreply).
Does NOT use Flask-Mail (no connect timeout → can spin forever).
"""
from __future__ import annotations

import os
import smtplib
import ssl
from contextlib import contextmanager
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
        'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_DEFAULT_SENDER',
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
    CERTIFICATE_VERIFY_FAILED / hostname mismatch for smtp.gmail.com.
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


def _build_message(subject: str, sender: str, recipient: str, text_body: str, html_body: str | None):
    from email.utils import formatdate, make_msgid

    if html_body:
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(text_body or '', 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    else:
        msg = MIMEText(text_body or '', 'plain', 'utf-8')

    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = sender
    msg['To'] = recipient
    msg['Date'] = formatdate(localtime=True)
    # Help cPanel/Exim treat this as system mail, not bulk spam
    msg['Auto-Submitted'] = 'auto-generated'
    msg['X-Auto-Response-Suppress'] = 'All'
    # Domain part of Message-ID helps some filters; derive from sender address
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
    # cPanel / .env paste artifacts: "secret" or 'secret'
    if len(pw) >= 2 and pw[0] == pw[-1] and pw[0] in ('"', "'"):
        pw = pw[1:-1].strip()
    # Zero-width / BOM that break SMTP AUTH
    for ch in ('\ufeff', '\u200b', '\u200c', '\u200d', '\u00a0'):
        pw = pw.replace(ch, '')
    # "xxxx xxxx xxxx xxxx" → "xxxxxxxxxxxxxxxx"
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
    # Brevo-only hints
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


def send_recovery_email(subject: str, recipient: str, text_body: str, html_body: str | None = None) -> None:
    """
    Send one password-reset email via MAIL_* SMTP (short timeout).
    One fallback to NOTIFICATION_MAIL_* (noreply). No Flask-Mail (hang risk).

    MAIL_USERNAME = SMTP login; MAIL_DEFAULT_SENDER = From address.
    They may differ (Brevo). On cPanel localhost they are usually the same.
    """
    _sync_mail_from_os_environ()
    recipient = (recipient or '').strip()
    if not recipient:
        raise RuntimeError('Missing recipient email')

    errors = []

    # Auth user and From may differ (Brevo: xxx@smtp-brevo.com vs recovery@domain).
    # cPanel localhost usually uses the same mailbox for both.
    mail_user = (_mail_setting('MAIL_USERNAME') or '').strip()
    sender = (_mail_setting('MAIL_DEFAULT_SENDER') or '').strip() or mail_user
    if sender:
        try:
            host = (_mail_setting('MAIL_SERVER') or 'localhost').strip()
            port = int(_mail_setting('MAIL_PORT') or 25)
            use_tls = _mail_bool('MAIL_USE_TLS', False)
            use_ssl = _mail_bool('MAIL_USE_SSL', False)
            if port == 465:
                use_ssl = True
                use_tls = False
            elif port == 587 and not use_ssl:
                use_tls = True
            msg = _build_message(subject, sender, recipient, text_body, html_body)
            msg['Reply-To'] = sender
            with _smtp_session(
                host=host,
                port=port,
                user=mail_user or sender,
                password=_mail_setting('MAIL_PASSWORD'),
                use_tls=use_tls,
                use_ssl=use_ssl,
            ) as smtp:
                smtp.sendmail(sender, [recipient], msg.as_bytes())
            return
        except Exception as smtp_err:
            diag = _smtp_auth_diag(mail_user or sender, _mail_setting('MAIL_PASSWORD'), host)
            errors.append(
                f'MAIL_* ({_mail_setting("MAIL_SERVER")}:{_mail_setting("MAIL_PORT")}): {smtp_err} [{diag}]'
            )
            current_app.logger.warning(f"recovery SMTP (MAIL_*) failed: {smtp_err} | {diag}")

    # Single fallback: noreply / notification channel
    try:
        from utils.notification_email import (
            _notification_smtp_configured,
            _notif_setting,
        )
        if _notification_smtp_configured():
            notif_user = (_notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
            notif_sender = (
                (_notif_setting('NOTIFICATION_MAIL_SENDER') or '').strip() or notif_user
            )
            if notif_sender:
                host = _notif_setting('NOTIFICATION_MAIL_SERVER') or current_app.config.get('MAIL_SERVER') or 'localhost'
                port = int(_notif_setting('NOTIFICATION_MAIL_PORT') or current_app.config.get('MAIL_PORT') or 25)
                use_tls = str(_notif_setting('NOTIFICATION_MAIL_USE_TLS', False)).lower() in (
                    '1', 'true', 'yes', 'on',
                )
                use_ssl = str(_notif_setting('NOTIFICATION_MAIL_USE_SSL', False)).lower() in (
                    '1', 'true', 'yes', 'on',
                )
                if port == 465:
                    use_ssl = True
                    use_tls = False
                elif port == 587 and not use_ssl:
                    use_tls = True
                mime = _build_message(subject, notif_sender, recipient, text_body or '', html_body)
                mime['Reply-To'] = notif_sender
                with _smtp_session(
                    host=host,
                    port=port,
                    user=notif_user or notif_sender,
                    password=_notif_setting('NOTIFICATION_MAIL_PASSWORD'),
                    use_tls=use_tls,
                    use_ssl=use_ssl,
                ) as smtp:
                    smtp.sendmail(notif_sender, [recipient], mime.as_bytes())
                current_app.logger.info('password reset sent via NOTIFICATION_MAIL_* fallback')
                return
    except Exception as notif_err:
        errors.append(f'NOTIFICATION_MAIL_*: {notif_err}')
        current_app.logger.warning(f"recovery SMTP (NOTIFICATION_MAIL_*) failed: {notif_err}")

    raise RuntimeError(' | '.join(errors) if errors else 'Email send failed (no SMTP configured)')

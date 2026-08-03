"""
Send app notification emails (marks revealed, etc.) via NOTIFICATION_MAIL_* (e.g. noreply@).
Password reset continues to use Flask-Mail + MAIL_* (e.g. recovery@) in auth blueprint.

Reads NOTIFICATION_* from os.environ first, then Flask app.config (cPanel sometimes injects
env only into the process environment).
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


def _sync_notification_mail_from_os_environ():
    """
    Copy NOTIFICATION_MAIL_* from os.environ into app.config each send.
    Fixes cases where app.config was populated before cPanel/Passenger env was visible.
    """
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        return
    prefix = 'NOTIFICATION_MAIL_'
    for k, v in os.environ.items():
        if not k.startswith(prefix):
            continue
        if v is None:
            continue
        sv = str(v)
        if sv.strip() == '':
            continue
        if k.endswith('_PASSWORD'):
            app.config[k] = sv.rstrip('\r\n')
        else:
            app.config[k] = sv.strip()


def _notif_setting(key: str, default=None):
    """Prefer OS env (cPanel), then app.config."""
    v = os.environ.get(key)
    if v is not None and str(v).strip() != '':
        return v
    v = current_app.config.get(key)
    if v is not None and v != '':
        return v
    return default


def _user_intends_notification_mail_channel() -> bool:
    """True if env/config suggests noreply / NOTIFICATION channel should be used."""
    s = (_notif_setting('NOTIFICATION_MAIL_SENDER') or '').strip()
    u = (_notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
    return bool(s or u)


def _notification_smtp_configured() -> bool:
    _sync_notification_mail_from_os_environ()
    user = (_notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
    pwd = _notif_setting('NOTIFICATION_MAIL_PASSWORD')
    if isinstance(pwd, str):
        pwd = pwd.rstrip('\r\n')
    # Password can be short or start with @; only reject None / empty / whitespace-only
    pwd_ok = pwd is not None and str(pwd).strip() != ''
    sender = (_notif_setting('NOTIFICATION_MAIL_SENDER') or _notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
    return bool(user and pwd_ok and sender)


@contextmanager
def _notification_smtp_session():
    _sync_notification_mail_from_os_environ()
    cfg = current_app.config
    host = _notif_setting('NOTIFICATION_MAIL_SERVER') or cfg.get('MAIL_SERVER') or 'localhost'
    port_raw = _notif_setting('NOTIFICATION_MAIL_PORT')
    port = int(port_raw) if port_raw else int(cfg.get('MAIL_PORT') or 25)
    user = (_notif_setting('NOTIFICATION_MAIL_USERNAME') or '').strip()
    password = _notif_setting('NOTIFICATION_MAIL_PASSWORD')
    use_tls = str(_notif_setting('NOTIFICATION_MAIL_USE_TLS', cfg.get('NOTIFICATION_MAIL_USE_TLS'))).lower() in (
        '1', 'true', 'yes', 'on',
    )
    use_ssl = str(_notif_setting('NOTIFICATION_MAIL_USE_SSL', cfg.get('NOTIFICATION_MAIL_USE_SSL'))).lower() in (
        '1', 'true', 'yes', 'on',
    )
    from utils.recovery_email import _normalize_mail_password, _normalize_smtp_security, _ssl_context
    password = _normalize_mail_password(password)
    host, port, use_tls, use_ssl = _normalize_smtp_security(host, port, use_tls, use_ssl)

    # Shared hosts often break CA verification for smtp.gmail.com (hostname mismatch)
    context = _ssl_context()

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=60, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=60)
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
            server.login(user, password)
        yield server
    finally:
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass


def _build_mime_message(subject: str, sender: str, recipient: str, text_body: str, html_body: str | None):
    from email.utils import formatdate, make_msgid

    msg = MIMEMultipart('alternative')
    msg['Subject'] = Header(subject or '', 'utf-8')
    msg['From'] = sender
    msg['To'] = recipient
    msg['Date'] = formatdate(localtime=True)
    domain = 'localhost'
    if '@' in (sender or ''):
        domain = sender.rsplit('@', 1)[-1].strip('>')
    msg['Message-ID'] = make_msgid(domain=domain)
    msg.attach(MIMEText(text_body or '', 'plain', 'utf-8'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    return msg


def _entry_subject(entry: dict, default_subject: str | None) -> str:
    return (entry.get('subject') or default_subject or '').strip() or 'AMS notification'


def _send_via_flask_mail(subject: str | None, entries: list[dict], sender_override: str | None = None) -> int:
    """Fallback sender using Flask-Mail channel."""
    from flask_mail import Message
    from extensions import mail

    cfg = current_app.config
    sent = 0
    fallback_sender = sender_override or cfg.get('MAIL_DEFAULT_SENDER') or cfg.get('MAIL_USERNAME')
    for entry in entries:
        recipient = (entry.get('recipient') or '').strip()
        if not recipient:
            continue
        try:
            msg = Message(
                subject=_entry_subject(entry, subject),
                recipients=[recipient],
                body=entry.get('text_body') or '',
                html=entry.get('html_body'),
                sender=fallback_sender,
            )
            mail.send(msg)
            sent += 1
        except Exception as one_err:
            current_app.logger.error(
                f"notification email (legacy) failed to {recipient}: {one_err}",
                exc_info=True,
            )
    return sent


def send_notification_batch(subject: str | None, entries: list[dict]) -> int:
    """
    Send one email per entry (privacy). Each entry: recipient (str), text_body,
    html_body (optional), subject (optional; overrides batch subject).

    Uses NOTIFICATION_MAIL_* SMTP when configured; otherwise Flask-Mail + MAIL_* (legacy).
    Returns number of messages accepted by SMTP / sent via Flask-Mail.
    """
    if not entries:
        return 0

    _sync_notification_mail_from_os_environ()

    cfg = current_app.config
    sent = 0

    use_smtp = _notification_smtp_configured()
    intends = _user_intends_notification_mail_channel()
    current_app.logger.info(
        f"notification email path: {'NOTIFICATION_SMTP (noreply)' if use_smtp else 'LEGACY Flask-Mail (MAIL_*)'}"
        f"; intends_notification_channel={intends}"
    )

    notification_sender = (
        (_notif_setting('NOTIFICATION_MAIL_SENDER') or _notif_setting('NOTIFICATION_MAIL_USERNAME') or '')
        .strip()
    )
    if intends and not use_smtp:
        current_app.logger.warning(
            "NOTIFICATION mail looks partially configured; using Flask-Mail fallback with "
            f"sender={notification_sender or 'MAIL_DEFAULT_SENDER'}"
        )
        return _send_via_flask_mail(subject, entries, sender_override=notification_sender or None)

    if use_smtp:
        # From may differ from SMTP login (Brevo); prefer explicit SENDER
        sender = (
            (_notif_setting('NOTIFICATION_MAIL_SENDER') or _notif_setting('NOTIFICATION_MAIL_USERNAME') or '')
            .strip()
        )
        try:
            with _notification_smtp_session() as smtp:
                for entry in entries:
                    recipient = (entry.get('recipient') or '').strip()
                    if not recipient:
                        continue
                    text_body = entry.get('text_body') or ''
                    html_body = entry.get('html_body')
                    try:
                        mime = _build_mime_message(
                            _entry_subject(entry, subject),
                            sender,
                            recipient,
                            text_body,
                            html_body,
                        )
                        mime['Reply-To'] = sender
                        smtp.sendmail(sender, [recipient], mime.as_bytes())
                        sent += 1
                    except Exception as one_err:
                        current_app.logger.error(
                            f"notification email failed to {recipient}: {one_err}",
                            exc_info=True,
                        )
        except Exception as conn_err:
            current_app.logger.error(f"notification SMTP session failed: {conn_err}", exc_info=True)
        if sent == 0 and entries:
            current_app.logger.warning(
                "NOTIFICATION SMTP sent 0 messages; trying Flask-Mail fallback with notification sender."
            )
            return _send_via_flask_mail(subject, entries, sender_override=notification_sender or None)
        return sent

    # Legacy / dev: no NOTIFICATION credentials
    return _send_via_flask_mail(subject, entries)

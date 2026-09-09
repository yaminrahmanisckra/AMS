"""CONF-07 / 1.12: SMTP TLS verify defaults on; sendmail off."""
import os
import ssl

from utils.recovery_email import _ssl_context, _ssl_verify_enabled


def test_ssl_verify_defaults_on(monkeypatch):
    monkeypatch.delenv('MAIL_SSL_VERIFY', raising=False)
    monkeypatch.setenv('CPANEL', '1')
    assert _ssl_verify_enabled() is True
    ctx = _ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_ssl_verify_can_be_disabled(monkeypatch):
    monkeypatch.setenv('MAIL_SSL_VERIFY', 'false')
    assert _ssl_verify_enabled() is False
    ctx = _ssl_context()
    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False


def test_ssl_verify_explicit_true(monkeypatch):
    monkeypatch.setenv('MAIL_SSL_VERIFY', 'true')
    monkeypatch.setenv('CPANEL', '1')
    assert _ssl_verify_enabled() is True

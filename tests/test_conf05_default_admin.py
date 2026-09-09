"""CONF-05: no hard-coded admin123 creator; production wipe scripts abort."""
import os
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash, check_password_hash

from utils.default_accounts import has_known_default_password, is_bootstrap_admin_identity
from utils.security_config import looks_like_production, refuse_destructive_in_production

ROOT = Path(__file__).resolve().parents[1]


def test_reset_script_does_not_hardcode_admin123():
    text = (ROOT / 'reset_database_complete.py').read_text(encoding='utf-8')
    assert 'admin123' not in text
    assert 'admin@example.com' not in text


def test_bootstrap_identity_and_default_password():
    assert is_bootstrap_admin_identity('admin', 'someone@x.test')
    assert is_bootstrap_admin_identity('other', 'admin@example.com')
    assert not is_bootstrap_admin_identity('head', 'head@kulawams.xyz')

    hashed = generate_password_hash('admin123', method='pbkdf2:sha512', salt_length=16)
    assert has_known_default_password(lambda pw: check_password_hash(hashed, pw))
    other = generate_password_hash('not-the-default-password', method='pbkdf2:sha512', salt_length=16)
    assert not has_known_default_password(lambda pw: check_password_hash(other, pw))


def test_looks_like_production_from_cpanel_env(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'development')
    monkeypatch.delenv('CPANEL', raising=False)
    monkeypatch.delenv('MYSQL', raising=False)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr(os, 'getcwd', lambda: '/tmp/ams-dev')
    assert not looks_like_production('/tmp/ams-dev/reset.py')

    monkeypatch.setenv('CPANEL', '1')
    assert looks_like_production()


def test_looks_like_production_from_public_html(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'development')
    monkeypatch.delenv('CPANEL', raising=False)
    monkeypatch.delenv('MYSQL', raising=False)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr(os, 'getcwd', lambda: '/home/kulawams/public_html/ams')
    assert looks_like_production()


def test_refuse_destructive_in_production(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('AMS_ALLOW_DESTRUCTIVE', raising=False)
    with pytest.raises(SystemExit) as exc:
        refuse_destructive_in_production()
    assert exc.value.code == 2

    monkeypatch.setenv('AMS_ALLOW_DESTRUCTIVE', '1')
    refuse_destructive_in_production()

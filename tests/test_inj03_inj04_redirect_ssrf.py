"""INJ-03 / INJ-04: safe redirects and AI URL SSRF guards."""
import pytest
from flask import Flask

from utils.ai.url_safety import (
    AIURLSafetyError,
    resolve_provider_base_url,
    sanitize_ai_base_url,
    validate_ai_http_url,
)
from utils.safe_redirect import safe_next_url, safe_redirect_target


def test_safe_next_url_relative_ok():
    assert safe_next_url('/admission/cycle/1') == '/admission/cycle/1'
    assert safe_next_url('/x?y=1') == '/x?y=1'


def test_safe_next_url_rejects_open_redirect():
    assert safe_next_url('https://evil.example/phish') is None
    assert safe_next_url('//evil.example/phish') is None
    assert safe_next_url('/\\evil.example') is None
    assert safe_next_url('\\evil') is None


def test_safe_redirect_target_same_host_absolute():
    app = Flask('redir_test')
    with app.test_request_context('/', base_url='https://kulawams.xyz'):
        assert safe_redirect_target(
            'https://kulawams.xyz/admission/x',
            fallback='/fallback',
        ) == '/admission/x'
        assert safe_redirect_target(
            'https://evil.example/phish',
            fallback='/fallback',
        ) == '/fallback'
        assert safe_redirect_target(None, fallback='/fallback') == '/fallback'


def test_ai_url_requires_https(monkeypatch):
    monkeypatch.setattr(
        'utils.ai.url_safety._hostname_resolves_public',
        lambda host: None,
    )
    with pytest.raises(AIURLSafetyError):
        validate_ai_http_url('http://api.openai.com/v1', provider='openai')


def test_ai_url_rejects_private_and_unknown_hosts(monkeypatch):
    monkeypatch.setattr(
        'utils.ai.url_safety._hostname_resolves_public',
        lambda host: None,
    )
    with pytest.raises(AIURLSafetyError):
        validate_ai_http_url('https://127.0.0.1/v1', provider='openai')
    with pytest.raises(AIURLSafetyError):
        validate_ai_http_url('https://evil.example/v1', provider='openai')
    with pytest.raises(AIURLSafetyError):
        sanitize_ai_base_url('https://metadata.google.internal/', provider='gemini')


def test_ai_url_allows_official_hosts(monkeypatch):
    monkeypatch.setattr(
        'utils.ai.url_safety._hostname_resolves_public',
        lambda host: None,
    )
    assert validate_ai_http_url('https://api.openai.com/v1', provider='openai') == (
        'https://api.openai.com/v1'
    )
    assert resolve_provider_base_url('deepseek', None) == 'https://api.deepseek.com/v1'
    assert resolve_provider_base_url('gemini', '') == (
        'https://generativelanguage.googleapis.com/v1beta'
    )


def test_ai_url_blocks_private_dns(monkeypatch):
    def fake_resolve(host):
        raise AIURLSafetyError('AI host resolves to a blocked address (127.0.0.1).')

    monkeypatch.setattr('utils.ai.url_safety._hostname_resolves_public', fake_resolve)
    with pytest.raises(AIURLSafetyError):
        validate_ai_http_url('https://api.openai.com/v1', provider='openai')

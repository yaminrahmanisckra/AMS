"""SSRF guards for AI provider HTTP calls (INJ-04)."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

# Canonical defaults (also used when api_base_url is empty).
DEFAULT_AI_BASE_URLS = {
    'openai': 'https://api.openai.com/v1',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta',
    'anthropic': 'https://api.anthropic.com/v1',
    'deepseek': 'https://api.deepseek.com/v1',
}

ALLOWED_AI_HOSTS = {
    'openai': frozenset({'api.openai.com'}),
    'gemini': frozenset({'generativelanguage.googleapis.com'}),
    'anthropic': frozenset({'api.anthropic.com'}),
    'deepseek': frozenset({'api.deepseek.com'}),
}

ALL_ALLOWED_AI_HOSTS = frozenset().union(*ALLOWED_AI_HOSTS.values())


class AIURLSafetyError(ValueError):
    """Raised when an AI base/request URL is not safe to fetch."""


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _hostname_resolves_public(hostname: str) -> None:
    """Resolve hostname and reject if any address is non-public."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AIURLSafetyError(f'Could not resolve AI host: {hostname}') from exc
    if not infos:
        raise AIURLSafetyError(f'Could not resolve AI host: {hostname}')
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_str = sockaddr[0]
        if _is_blocked_ip(ip_str):
            raise AIURLSafetyError(
                f'AI host resolves to a blocked address ({ip_str}). '
                'Only public provider endpoints are allowed.'
            )


def validate_ai_http_url(url: str, *, provider: str | None = None) -> str:
    """Validate a full request URL (base + path). Returns normalized URL string.

    Rules: https only, allowlisted host, no credentials, public DNS only.
    """
    if not url or not isinstance(url, str):
        raise AIURLSafetyError('AI URL is empty.')
    raw = url.strip()
    try:
        parsed = urlparse(raw)
    except Exception as exc:
        raise AIURLSafetyError('AI URL is invalid.') from exc

    if parsed.scheme.lower() != 'https':
        raise AIURLSafetyError('AI URL must use https://')
    if parsed.username or parsed.password:
        raise AIURLSafetyError('AI URL must not contain credentials.')
    host = (parsed.hostname or '').lower().rstrip('.')
    if not host:
        raise AIURLSafetyError('AI URL is missing a host.')
    # Reject literal IPs — allowlist is hostname-only.
    try:
        ipaddress.ip_address(host)
        raise AIURLSafetyError('AI URL must use a provider hostname, not an IP address.')
    except ValueError:
        pass

    provider_key = (provider or '').strip().lower()
    allowed = ALLOWED_AI_HOSTS.get(provider_key, ALL_ALLOWED_AI_HOSTS)
    if host not in allowed:
        raise AIURLSafetyError(
            f'AI host “{host}” is not allowed. '
            f'Use the official endpoint for this provider.'
        )

    _hostname_resolves_public(host)

    # Rebuild without fragment; keep path/query/port (port rare for these APIs).
    netloc = host
    if parsed.port and parsed.port != 443:
        # Non-default ports on allowlisted hosts are unusual — block to reduce surprise.
        raise AIURLSafetyError('AI URL must use the default HTTPS port (443).')
    normalized = urlunparse(('https', netloc, parsed.path or '', '', parsed.query, ''))
    return normalized.rstrip('/') if not parsed.query else normalized


def sanitize_ai_base_url(url: str | None, *, provider: str | None = None) -> str | None:
    """Clean optional admin-configured base URL; None if unset.

    Empty / literal None → None. Otherwise must pass ``validate_ai_http_url``.
    """
    if url is None:
        return None
    cleaned = str(url).strip().rstrip('/')
    if not cleaned or cleaned.lower() in ('none', 'null', 'undefined', 'n/a'):
        return None
    return validate_ai_http_url(cleaned, provider=provider)


def resolve_provider_base_url(provider: str, api_base_url: str | None) -> str:
    """Return validated base URL for a provider (custom or default)."""
    provider_key = (provider or '').strip().lower()
    custom = sanitize_ai_base_url(api_base_url, provider=provider_key)
    if custom:
        return custom
    default = DEFAULT_AI_BASE_URLS.get(provider_key)
    if not default:
        # Unknown provider — still require allowlisted URL if somehow supplied.
        raise AIURLSafetyError(f'Unknown AI provider: {provider_key or "(empty)"}')
    return validate_ai_http_url(default, provider=provider_key)

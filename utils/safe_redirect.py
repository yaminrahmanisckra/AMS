"""Open-redirect guards (INJ-03).

Accept only same-site relative paths or absolute URLs whose host matches
the current request host. Never trust raw ``request.referrer`` / ``next``.
"""
from __future__ import annotations

from urllib.parse import urlparse


def safe_next_url(next_url: str | None) -> str | None:
    """Return a safe relative path, or None.

    Same rules as the historical ``app._safe_next_url`` helper: only paths
    that start with a single ``/`` (no scheme-relative ``//``).
    """
    if not next_url or not isinstance(next_url, str):
        return None
    next_url = next_url.strip()
    if not next_url.startswith('/') or next_url.startswith('//'):
        return None
    if next_url.startswith('/\\') or next_url.startswith('\\'):
        return None
    # Reject backslashes in the path portion (some browsers normalize \\ → /).
    path_only = next_url.split('?', 1)[0].split('#', 1)[0]
    if '\\' in path_only:
        return None
    return next_url


def safe_redirect_target(candidate: str | None, *, fallback: str | None = None) -> str | None:
    """Safe target for ``redirect(...)`` from referrer / next / etc.

    - Relative same-site paths → returned as-is (via ``safe_next_url``).
    - Absolute http(s) URLs → allowed only when netloc matches ``request.host``;
      returns path + query (relative) so the Location header stays same-origin.
    - Anything else → ``fallback``.
    """
    if not candidate or not isinstance(candidate, str):
        return fallback
    candidate = candidate.strip()
    if not candidate:
        return fallback

    relative = safe_next_url(candidate)
    if relative is not None:
        return relative

    try:
        parsed = urlparse(candidate)
    except Exception:
        return fallback

    if parsed.scheme not in ('http', 'https'):
        return fallback
    if not parsed.netloc:
        return fallback

    try:
        from flask import has_request_context, request

        if not has_request_context():
            return fallback
        req_host = (request.host or '').lower()
    except Exception:
        return fallback

    ref_host = (parsed.netloc or '').lower()
    if not req_host or ref_host != req_host:
        return fallback

    path = parsed.path or '/'
    if not path.startswith('/') or path.startswith('//'):
        return fallback
    if '\\' in path:
        return fallback
    query = f'?{parsed.query}' if parsed.query else ''
    fragment = f'#{parsed.fragment}' if parsed.fragment else ''
    # Drop fragment for redirects (not sent to server anyway); keep query.
    return path + query

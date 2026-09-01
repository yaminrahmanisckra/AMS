"""Client IP after ProxyFix (see utils.security_config.apply_proxy_fix)."""


def client_ip() -> str:
    """TCP peer, or the trusted proxy hop. Do not parse X-Forwarded-For here."""
    from flask import request
    return (request.remote_addr or '').strip()

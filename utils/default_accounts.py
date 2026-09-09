"""Known leftover bootstrap accounts from old reset scripts (CONF-05)."""
from __future__ import annotations

BOOTSTRAP_ADMIN_USERNAMES = frozenset({'admin'})
BOOTSTRAP_ADMIN_EMAILS = frozenset({'admin@example.com'})
KNOWN_DEFAULT_PASSWORDS = ('admin123',)


def is_bootstrap_admin_identity(username, email) -> bool:
    user = (username or '').strip().lower()
    mail = (email or '').strip().lower()
    return user in BOOTSTRAP_ADMIN_USERNAMES or mail in BOOTSTRAP_ADMIN_EMAILS


def has_known_default_password(check_password) -> bool:
    if not callable(check_password):
        return False
    for candidate in KNOWN_DEFAULT_PASSWORDS:
        try:
            if check_password(candidate):
                return True
        except Exception:
            continue
    return False

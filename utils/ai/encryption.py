"""Encrypt/decrypt AI API keys at rest.

Uses AI_KEY_ENCRYPTION_SECRET when set. Decrypt dual-reads the dedicated secret
first, then falls back to SECRET_KEY-derived Fernet so SECRET_KEY can be rotated
without permanently destroying stored keys. Re-encrypt rows under the new secret
before dropping the SECRET_KEY fallback.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet_from_secret(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode('utf-8')).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _secrets_to_try():
    """Ordered secrets for decrypt: dedicated first, then SECRET_KEY legacy."""
    secrets = []
    dedicated = current_app.config.get('AI_KEY_ENCRYPTION_SECRET') or ''
    if dedicated.strip():
        secrets.append(dedicated.strip())
    legacy = current_app.config.get('SECRET_KEY', 'a_very_secret_default_key')
    if legacy and legacy not in secrets:
        secrets.append(legacy)
    if not secrets:
        secrets.append('a_very_secret_default_key')
    return secrets


def _fernet_for_encrypt():
    """Encrypt with dedicated secret when configured, else SECRET_KEY."""
    dedicated = (current_app.config.get('AI_KEY_ENCRYPTION_SECRET') or '').strip()
    if dedicated:
        return _fernet_from_secret(dedicated)
    legacy = current_app.config.get('SECRET_KEY', 'a_very_secret_default_key')
    return _fernet_from_secret(legacy)


def encrypt_api_key(plain_text):
    if not plain_text:
        return None
    return _fernet_for_encrypt().encrypt(plain_text.strip().encode('utf-8')).decode('utf-8')


def decrypt_api_key(cipher_text):
    if not cipher_text:
        return None
    raw = cipher_text.encode('utf-8')
    for secret in _secrets_to_try():
        try:
            return _fernet_from_secret(secret).decrypt(raw).decode('utf-8')
        except (InvalidToken, ValueError, TypeError):
            continue
    return None


def mask_api_key(plain_text):
    if not plain_text:
        return ''
    text = plain_text.strip()
    if len(text) <= 8:
        return '****'
    return f'{text[:4]}...{text[-4:]}'


def reencrypt_api_key(cipher_text):
    """Decrypt (dual-read) and re-encrypt under the current encrypt secret."""
    plain = decrypt_api_key(cipher_text)
    if plain is None:
        return None
    return encrypt_api_key(plain)

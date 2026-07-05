"""Encrypt/decrypt AI API keys at rest."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet():
    secret = current_app.config.get('SECRET_KEY', 'a_very_secret_default_key')
    digest = hashlib.sha256(secret.encode('utf-8')).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_api_key(plain_text):
    if not plain_text:
        return None
    return _fernet().encrypt(plain_text.strip().encode('utf-8')).decode('utf-8')


def decrypt_api_key(cipher_text):
    if not cipher_text:
        return None
    try:
        return _fernet().decrypt(cipher_text.encode('utf-8')).decode('utf-8')
    except (InvalidToken, ValueError, TypeError):
        return None


def mask_api_key(plain_text):
    if not plain_text:
        return ''
    text = plain_text.strip()
    if len(text) <= 8:
        return '****'
    return f'{text[:4]}...{text[-4:]}'

#!/usr/bin/env python3
"""Re-encrypt AI provider API keys under AI_KEY_ENCRYPTION_SECRET.

Run AFTER setting AI_KEY_ENCRYPTION_SECRET in the environment (keeping the
current SECRET_KEY) and BEFORE rotating SECRET_KEY. Decrypt dual-reads the
dedicated secret first, then falls back to SECRET_KEY.

  cd /home/kulawams/public_html/ams
  source /home/kulawams/virtualenv/public_html/ams/3.12/bin/activate
  python scripts/security/reencrypt_ai_keys.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, '.env'))
    extra = os.path.expanduser('~/ams.env')
    if os.path.isfile(extra):
        load_dotenv(extra)
except ImportError:
    pass


def main():
    from utils.security_config import INSECURE_SECRET_KEYS

    dedicated = (os.getenv('AI_KEY_ENCRYPTION_SECRET') or '').strip()
    secret = (os.getenv('SECRET_KEY') or '').strip()
    print(
        'env: AI_KEY_ENCRYPTION_SECRET=%s SECRET_KEY=%s (len=%s)'
        % (
            'set' if dedicated else 'MISSING',
            'set' if secret and secret not in INSECURE_SECRET_KEYS else 'missing/placeholder',
            len(secret) if secret else 0,
        )
    )
    if not dedicated:
        print('Set AI_KEY_ENCRYPTION_SECRET before running.', file=sys.stderr)
        return 1
    if not secret or secret in INSECURE_SECRET_KEYS or len(secret) < 16:
        print(
            'SSH does not inherit cPanel env. Export the CURRENT production SECRET_KEY '
            '(cPanel → Python App → Environment) in this shell, then retry. '
            'Do not generate a new SECRET_KEY yet.',
            file=sys.stderr,
        )
        return 1
    from app import create_app
    from extensions import db
    from utils.ai.encryption import decrypt_api_key, encrypt_api_key
    from utils.ai.models import AIProviderSetting

    app = create_app()
    with app.app_context():
        updated = 0
        skipped = 0
        rows = AIProviderSetting.query.filter(
            AIProviderSetting.api_key_encrypted.isnot(None)
        ).all()
        for row in rows:
            plain = decrypt_api_key(row.api_key_encrypted)
            if not plain:
                print(f'id={row.id}: decrypt failed — skip')
                skipped += 1
                continue
            row.api_key_encrypted = encrypt_api_key(plain)
            updated += 1
        db.session.commit()
        print(f'Re-encrypted {updated} AIProviderSetting rows ({skipped} skipped)')
        if skipped:
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

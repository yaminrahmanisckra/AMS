#!/usr/bin/env python3
"""Re-encrypt AI provider API keys under AI_KEY_ENCRYPTION_SECRET.

Run AFTER setting AI_KEY_ENCRYPTION_SECRET in the environment and BEFORE
rotating SECRET_KEY. Uses dual-read decrypt then re-encrypt.

  AI_KEY_ENCRYPTION_SECRET=... DATABASE_URL=... python scripts/security/reencrypt_ai_keys.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

os.environ.setdefault('FLASK_ENV', 'development')


def main():
    if not (os.getenv('AI_KEY_ENCRYPTION_SECRET') or '').strip():
        print('Set AI_KEY_ENCRYPTION_SECRET before running.', file=sys.stderr)
        return 1
    from app import create_app
    from extensions import db
    app = create_app()
    with app.app_context():
        from utils.ai.encryption import decrypt_api_key, encrypt_api_key
        try:
            from blueprints.class_management.models import AIProviderSetting
        except Exception:
            # Fallback model location
            from sqlalchemy import text
            rows = db.session.execute(text(
                'SELECT id, api_key_encrypted FROM ai_provider_setting WHERE api_key_encrypted IS NOT NULL'
            )).fetchall()
            updated = 0
            for row in rows:
                plain = decrypt_api_key(row.api_key_encrypted)
                if not plain:
                    print(f'id={row.id}: decrypt failed — skip')
                    continue
                new_cipher = encrypt_api_key(plain)
                db.session.execute(
                    text('UPDATE ai_provider_setting SET api_key_encrypted = :c WHERE id = :id'),
                    {'c': new_cipher, 'id': row.id},
                )
                updated += 1
            db.session.commit()
            print(f'Re-encrypted {updated} rows via SQL')
            return 0

        updated = 0
        for row in AIProviderSetting.query.filter(AIProviderSetting.api_key_encrypted.isnot(None)).all():
            plain = decrypt_api_key(row.api_key_encrypted)
            if not plain:
                print(f'id={row.id}: decrypt failed — skip')
                continue
            row.api_key_encrypted = encrypt_api_key(plain)
            updated += 1
        db.session.commit()
        print(f'Re-encrypted {updated} AIProviderSetting rows')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

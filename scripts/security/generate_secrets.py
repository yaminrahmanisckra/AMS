#!/usr/bin/env python3
"""Print new SECRET_KEY and AI_KEY_ENCRYPTION_SECRET. Do not save these to disk."""
import secrets

print('SECRET_KEY=' + secrets.token_urlsafe(64))
print('AI_KEY_ENCRYPTION_SECRET=' + secrets.token_urlsafe(64))
print('# Paste into cPanel → Python App → Environment Variables, then Restart.')
print('# Order: set AI_KEY_ENCRYPTION_SECRET first, re-encrypt AI keys, THEN replace SECRET_KEY.')

#!/usr/bin/env python3
"""Fail if Cursor debug leftovers, ngrok hacks, or /test_download return (LOG-02)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCAN_GLOBS = (
    'app.py',
    'app_self_assessment.py',
    'blueprints/**/*.py',
    'templates/**/*.html',
    'static/js/**/*.js',
)

SKIP_NAME_PARTS = (
    '/tests/',
    '/scripts/',
    '/venv',
    '__pycache__',
)

PATTERNS = (
    (re.compile(r'debug\.log'), 'writes Cursor debug.log'),
    (re.compile(r'#\s*#region agent log'), 'Cursor agent-log region'),
    (re.compile(r'/Users/isckra'), 'developer machine path'),
    (re.compile(r'\btest_download\b'), 'test_download leftover'),
    (re.compile(r'\bngrok\b', re.IGNORECASE), 'ngrok leftover'),
    (re.compile(r'force_logout'), 'force_logout leftover'),
)


def iter_scan_files():
    seen = set()
    for pattern in SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            rel = str(path.relative_to(ROOT)).replace('\\', '/')
            if any(part in f'/{rel}' for part in SKIP_NAME_PARTS):
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path, rel


def find_leftovers():
    hits = []
    for path, rel in iter_scan_files():
        for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            for regex, label in PATTERNS:
                if regex.search(line):
                    hits.append(f'{rel}:{lineno}: {label}: {line.strip()}')
                    break
    return hits


def main() -> int:
    hits = find_leftovers()
    if not hits:
        print('OK: no debug leftovers in scanned app files')
        return 0
    print('Debug leftovers (LOG-02):', file=sys.stderr)
    for hit in hits:
        print(f'  {hit}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail if route handlers send raw exception text to the browser (LOG-01)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCAN_GLOBS = (
    'app.py',
    'app_self_assessment.py',
    'blueprints/**/*.py',
)

SKIP_NAME_PARTS = (
    '/tests/',
    '/scripts/',
    '/venv',
    '__pycache__',
)

LEAK = re.compile(
    r"""
    (?:
        jsonify\(
        | flash\(
        | return\s+f['\"]
    )
    .{0,400}?
    (?:
        str\(\s*(?:e|exc|err|error|query_error|exec_error|json_error|commit_error|
            import_err|weasy_err|outer_error|delete_error|clear_exc|sync_exc)\s*\)
        | \{e\}
        | \{str\(e\)
        | \{str\(exc\)
    )
    """,
    re.VERBOSE | re.DOTALL,
)

FIELD_LEAK = re.compile(
    r"""['\"](?:error|message|detail|details)['\"]\s*:\s*
        (?:
            str\(\s*(?:e|exc|err|error|query_error|exec_error|json_error|commit_error|
                import_err|weasy_err|outer_error|delete_error)\s*\)
            | f['\"].*\{str\(
            | f['\"].*\{e\}
        )
    """,
    re.VERBOSE,
)

LOGGER_HINT = re.compile(
    r'logger\.|logging\.|print\(|f\.write\(|#endregion|#region',
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


def _stripped_code(line: str) -> str:
    if '#' in line:
        return line.split('#', 1)[0]
    return line


def find_leaks():
    hits = []
    for path, rel in iter_scan_files():
        text = path.read_text(encoding='utf-8')
        for lineno, line in enumerate(text.splitlines(), 1):
            code = _stripped_code(line)
            if LOGGER_HINT.search(code):
                continue
            if 'client_message(' in code or 'api_error(' in code or 'flash_exception(' in code:
                continue
            if 'report_exception(' in code:
                continue
            if LEAK.search(code) or FIELD_LEAK.search(code):
                hits.append(f'{rel}:{lineno}:{line.strip()}')
    return hits


def main() -> int:
    hits = find_leaks()
    if not hits:
        print('OK: no client-facing str(e) leaks in scanned routes')
        return 0
    print('Client-facing exception text (LOG-01):', file=sys.stderr)
    for hit in hits:
        print(f'  {hit}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

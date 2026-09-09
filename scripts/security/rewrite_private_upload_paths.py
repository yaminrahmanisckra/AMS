#!/usr/bin/env python3
"""Rewrite legacy /static/uploads/... DB paths to private-relative paths (FILE-01/02).

Safe to run after rsync into PRIVATE_UPLOAD_DIR. Default is dry-run.

Usage (from app root, with app env loaded):
  python scripts/security/rewrite_private_upload_paths.py --dry-run
  python scripts/security/rewrite_private_upload_paths.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys

# Allow running from repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _to_relative(stored: str | None) -> str | None:
    """Return private-relative path if ``stored`` is a legacy public uploads path."""
    if not stored:
        return None
    raw = str(stored).strip().replace('\\', '/').lstrip('/')
    if not raw:
        return None
    for prefix in ('static/uploads/', 'uploads/'):
        if raw.startswith(prefix):
            rel = raw[len(prefix):]
            if rel.startswith(('user_photos/', 'user_signatures/', 'admission_exam/')):
                return rel
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Commit updates (default: dry-run)')
    parser.add_argument('--dry-run', action='store_true', help='Print planned changes only')
    args = parser.parse_args()
    apply = bool(args.apply) and not args.dry_run

    from app import create_app
    from extensions import db
    from user_models import User

    app = create_app()
    changed = 0
    with app.app_context():
        users = User.query.all()
        for user in users:
            for field in ('photo', 'signature_path'):
                old = getattr(user, field, None)
                new = _to_relative(old)
                if new and new != old:
                    print(f'user {user.id} {field}: {old!r} -> {new!r}')
                    if apply:
                        setattr(user, field, new)
                    changed += 1

        try:
            from blueprints.admission_exam.models import AdmissionCandidate, AdmissionCycle
        except Exception as exc:
            print('skip admission models:', exc)
            AdmissionCandidate = AdmissionCycle = None  # type: ignore

        if AdmissionCandidate is not None:
            for cand in AdmissionCandidate.query.all():
                for field in ('photo_path', 'signature_path', 'bank_slip_path'):
                    old = getattr(cand, field, None)
                    new = _to_relative(old)
                    if new and new != old:
                        print(f'candidate {cand.id} {field}: {old!r} -> {new!r}')
                        if apply:
                            setattr(cand, field, new)
                        changed += 1
            for cycle in AdmissionCycle.query.all():
                old = getattr(cycle, 'chairman_signature_path', None)
                new = _to_relative(old)
                if new and new != old:
                    print(f'cycle {cycle.id} chairman_signature_path: {old!r} -> {new!r}')
                    if apply:
                        cycle.chairman_signature_path = new
                    changed += 1

        if apply:
            db.session.commit()
            print(f'Applied {changed} path update(s).')
        else:
            print(f'Dry-run: {changed} path update(s) would be applied. Re-run with --apply.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

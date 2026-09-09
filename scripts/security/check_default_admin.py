#!/usr/bin/env python3
"""Read-only check: leftover username `admin` / password admin123 (CONF-05).

Run on the production host (venv activated, app directory):

  cd /home/kulawams/public_html/ams
  source /home/kulawams/virtualenv/public_html/ams/3.12/bin/activate
  python scripts/security/check_default_admin.py

If a default password is found, set a new one (does not print the new password):

  python scripts/security/check_default_admin.py --set-password
"""
from __future__ import annotations

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


def _rows(users):
    from utils.default_accounts import has_known_default_password, is_bootstrap_admin_identity

    report = []
    for user in users:
        identity = is_bootstrap_admin_identity(user.username, user.email)
        weak = has_known_default_password(user.check_password)
        role = user.role or ''
        is_admin_role = 'admin' in role.lower()
        if identity or weak or is_admin_role:
            report.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': role,
                'default_identity': identity,
                'weak_password': weak,
            })
    return report


def _print_report(report):
    if not report:
        print('No admin-role users and no bootstrap identity found.')
        return
    print(f"{'id':>6}  {'username':<20}  {'role':<24}  default_id  weak_pw")
    for row in report:
        print(
            f"{row['id']:6d}  {row['username']:<20}  {row['role']:<24}  "
            f"{'YES' if row['default_identity'] else 'no':>10}  "
            f"{'YES' if row['weak_password'] else 'no':>7}"
        )


def _set_password(app, username=None):
    import getpass
    from user_models import User
    from extensions import db
    from utils.default_accounts import has_known_default_password

    with app.app_context():
        if username:
            user = User.query.filter_by(username=username).first()
        else:
            users = User.query.all()
            weak = [u for u in users if has_known_default_password(u.check_password)]
            if not weak:
                print('No account uses the known default password. Nothing to change.')
                return 0
            if len(weak) > 1:
                print('Several accounts use the default password:')
                for u in weak:
                    print(f'  {u.username}')
                print('Re-run with --set-password --username NAME')
                return 1
            user = weak[0]
        if not user:
            print('User not found.')
            return 1
        if not has_known_default_password(user.check_password):
            print(f"{user.username}: password is not the known default. Refusing to overwrite.")
            return 1
        new_pw = getpass.getpass(f'New password for {user.username}: ').strip()
        if len(new_pw) < 10:
            print('Password must be at least 10 characters.')
            return 1
        confirm = getpass.getpass('Confirm: ').strip()
        if new_pw != confirm:
            print('Passwords do not match.')
            return 1
        user.set_password(new_pw)
        user.must_change_password = True
        db.session.commit()
        print(f'Password updated for {user.username}. They must change it at next login.')
        return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    set_password = '--set-password' in argv
    username = None
    if '--username' in argv:
        idx = argv.index('--username')
        if idx + 1 >= len(argv):
            print('--username requires a value', file=sys.stderr)
            return 2
        username = argv[idx + 1]

    from app import create_app
    from user_models import User

    app = create_app()
    if set_password:
        return _set_password(app, username)

    with app.app_context():
        report = _rows(User.query.all())
    _print_report(report)
    if any(row['weak_password'] for row in report):
        print('\nWEAK PASSWORD FOUND. Change it now:')
        print('  python scripts/security/check_default_admin.py --set-password')
        return 2
    if any(row['default_identity'] for row in report):
        print('\nUsername/email matches the old bootstrap account. Prefer a unique operator username.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

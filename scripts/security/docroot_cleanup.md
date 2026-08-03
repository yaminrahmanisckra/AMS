# Phase 1 — Delete from live document root (before Phase 2 deny rules)

Remove these if present under the cPanel docroot (not needed at runtime):

- `kulawams.htaccess`, `.htaccess.kulawams`, `.htaccess.kulawams.fixed`
- Any `*.sql` at the site root (repo copies live under `scripts/sql/`)
- Deployment zips / leftover `*.md` runbooks if uploaded
- `app.pid`, stray `venv*`, `.git` worktree pointers
- Confirm `logs/`, `instance/*.db`, `*.log` are not HTTP-reachable after Phase 2

Do **not** delete the live `.htaccess` or `passenger_wsgi.py`.

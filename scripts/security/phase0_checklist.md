# Phase 0 — Safety net checklist (host)

Do these on cPanel before any schema or auth code deploy. Zero application-code risk.

1. **DB dump #1** — cPanel → Backup → Download MySQL Database Backup → save to local disk and `/home/<user>/ams_backups/`.
2. **Verify dump** — `gunzip -c ams_*.sql.gz | tail -3` must end with `-- Dump completed on`. Import into a scratch DB; compare row counts from `phase0_inventory.sql` query 7.
3. **DB dump #2** — phpMyAdmin → Export → Custom → SQL → gzip (independent path).
4. **Rollback store** — create `/home/<user>/ams_rollback/` outside the document root. Before every overwrite: copy to `ams_rollback/<timestamp>/<relative-path>`.
5. **Staging** — subdomain + separate DB; mail that cannot reach real students.
6. **Local SQLite copy** — for testing any global `before_request` before production.
7. **Inventory** — run `scripts/security/phase0_inventory.sql`; save outputs.
8. **pip freeze** — on the host venv: `pip freeze > /home/<user>/ams_backups/requirements.lock.txt` (local snapshot also under `docs/security/`).
9. **HTTPS** — confirm the site is only served over HTTPS before enabling `SESSION_COOKIE_SECURE`.

## Rotate before mail fix

Rotate the `recovery@kulawams.xyz` mailbox password in cPanel **before** correcting `Mail_SERVER` → `MAIL_SERVER` in `.htaccess`. Then set the new password only via cPanel env / private config — never commit it.

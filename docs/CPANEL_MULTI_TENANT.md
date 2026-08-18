# cPanel: second discipline tenant (MCJ and later)

Law stays on the existing Python App (`TENANT_CODE=law`, current `DATABASE_URL`).
Each additional discipline is a **separate cPanel Python App + separate MySQL database + separate subdomain**. The git repo is shared.

## 1. Create MySQL database

In cPanel → MySQL Databases, create an empty database (e.g. `user_mcj_ams`) and a user with full privileges. Do **not** copy the Law database.

## 2. Create Python App

- New domain/subdomain (e.g. `mcj.example.com`)
- Same Python version as Law (3.12)
- Document root: a checkout of this repo, **or** a symlink to the Law checkout plus a distinct `.env` / environment variables
- Set `VIRTUALENV_ACTIVATE` to this app’s `activate_this.py` if the default Law venv path would be wrong

## 3. Environment variables

Copy from Law, then change:

```
TENANT_CODE=mcj
DATABASE_URL=mysql+pymysql://USER:PASS@localhost/user_mcj_ams
PUBLIC_APP_URL=https://mcj.example.com
MAIL_USERNAME=recovery@mcj.example.com
MAIL_DEFAULT_SENDER=recovery@mcj.example.com
NOTIFICATION_MAIL_USERNAME=noreply@mcj.example.com
NOTIFICATION_MAIL_SENDER=noreply@mcj.example.com
CPANEL=1
SECRET_KEY=<new secret, not the Law key>
```

Install dependencies in the new venv (`pip install -r requirements.txt`), including `PyYAML`.

## 4. Schema and first admin

From the app directory, with the MCJ env loaded:

```
flask db upgrade
```

Create an admin user through your usual bootstrap process (same as a fresh Law install). Import MCJ curriculum/students later — never import Law rows into this database.

## 5. Branding and plugins

Edit `tenants/mcj/tenant.yaml` (name, course prefix, year map, feature flags, admission academic rows).
Surveys: `tenants/mcj/surveys/*.json` (generic packs; no Bar Council / Moot Court).
Curriculator layout: `tenants/mcj/curriculator.yaml`.
Optional template overrides: `tenants/mcj/templates/...` (Jinja ChoiceLoader, checked first).

## 6. Restart

cPanel → Setup Python App → Restart. Confirm the UI shows MCJ, not Law, and that logging into Law (`kulawams.xyz`) still shows Law data only.

## Adding another discipline

Copy `tenants/mcj/` to `tenants/<code>/`, adjust `tenant.yaml`, repeat steps 1–6 with `TENANT_CODE=<code>` and a new database.

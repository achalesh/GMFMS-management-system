# Phase 1 completion report

Date: 28 September 2026  
Workspace: D:\Gramaswaraj\Web  
Scope: **Phase 1 — Foundation only. Phase 2 has not begun.**

## Repository inspection

The directory was empty and was not a Git repository. There were no existing application files to modify or preserve. All project files were newly created. No commit was made because there is no initialized repository; no Git identity or remote was invented.

## Delivered

Python 3.12.14 virtual environment with Django 5.2.17; modular accounts, organization, audit and dashboard applications; custom responsive Bootstrap staff interface; local Bootstrap/HTMX assets; environment configuration; Django ORM migrations; custom UUID user; seven roles; per-role jurisdiction restrictions; audited settings; login/logout/reset/change-password; shared-database login/reset throttling; authenticated REST/OpenAPI foundation; production configuration guards; installation/security/deployment documentation.

The local database contains only seeded role/settings data and framework tables. No application administrator or default password was created. A random development SECRET_KEY was written to the ignored local .env without exposing it. Browser verification used a separate ignored database under artifacts/.

## Models added

1. User — UUID primary key, Django authentication, unique normalized email, preferred language.
2. Role — SUPER_ADMIN, STATE_ADMIN, DISTRICT_ADMIN, BLOCK_COORDINATOR, REVIEWER, ID_CARD_OPERATOR, VIEWER.
3. UserRole — assigned role, granting actor, active flag and timestamps.
4. UserJurisdiction — role-specific state/district/block scope, unique/shape constraints.
5. RequestBudget — atomic expiring password-reset request counter.
6. OrganizationSetting — singleton organization branding/contact record, optimistic revision.
7. SystemSetting — singleton policy/defaults record, optimistic revision.
8. AuditLog — append-only application events with actor and old/new values.

Framework authentication/session/admin tables and django-axes security tables are also migrated.

## Routes added

- / — staff overview
- /profile/ — own access
- /accounts/login/ and /accounts/logout/
- /accounts/password/change/
- /accounts/password/reset/ and its sent/confirm/complete routes
- /accounts/users/ — authorized staff directory
- /settings/organization/
- /settings/system/
- /audit/
- /admin/ — restricted emergency administration
- /api/v1/auth/me/
- /api/schema/ and /api/docs/
- /i18n/setlang/
- /health/

No public media route, registration endpoint, facilitator data or verification endpoint exists yet.

## Tests and checks executed

| Check | Result |
| --- | --- |
| Initial migrations generated | Passed |
| manage.py migrate | Applied all foundation/framework migrations |
| manage.py makemigrations --check --dry-run | No changes detected |
| manage.py test --settings=config.settings.test | **60 tests passed** |
| manage.py check | No issues |
| manage.py check --deploy with production settings and safe check-only environment | No issues |
| ruff check . | Passed |
| ruff format --check . | Passed |
| pip check | No broken requirements |
| manage.py spectacular --validate --fail-on-warn | Passed |
| manage.py collectstatic --noinput | Passed |
| Playwright browser checks against isolated QA database | Passed |
| Desktop/mobile screenshots visually inspected | Passed |

Tests cover district/block boundaries, mixed-role scope isolation, viewer/card-operator restrictions, anonymous/inactive/unassigned access, database constraints, audited grants/revocations, direct URL/POST denial, settings conflicts, atomic settings/audit rollback, immutable audit behavior, emergency admin creation/updates/deletion denial, email normalization, CSRF, password validation, login lockout/cooldown/IP bypass attempts, one-use reset tokens, reset throttling, session configuration, API field allowlisting, no-store headers, protected schema/docs, private-media absence and fail-fast production settings.

Browser checks exercised real password hashing and sessions, sign-in, settings save, sign-out, reset navigation, mobile menu behavior and horizontal-overflow assertions at **1440, 768, 390 and 360 pixels**. No JavaScript errors were observed. This verifies Chromium rendering at those sizes, not physical iPhone/Android devices.

Screenshots:
- [Desktop sign-in](artifacts/login-desktop.png)
- [Desktop dashboard](artifacts/dashboard-desktop.png)
- [Organization settings](artifacts/settings-desktop.png)
- [Mobile dashboard](artifacts/dashboard-390.png)
- [Mobile sign-in](artifacts/login-mobile.png)

## Commands to use this prepared workspace

~~~powershell
cd D:\Gramaswaraj\Web
.\.venv\Scripts\python.exe manage.py create_initial_admin
.\.venv\Scripts\python.exe manage.py runserver
~~~

Open http://127.0.0.1:8000/. The sign-in preview may already be running locally; avoid starting a second server on the same port. Initial administrator creation is interactive and requires your own email/password.

## Decisions and limits

No confirmation is needed to use this foundation. Before Phase 2, choose an authoritative, maintained Kerala district/block/Panchayat dataset. Current jurisdiction codes are interim authorization contracts and must be migrated to authoritative foreign keys; they are not a substitute for the location master.

PostgreSQL/MySQL server integration and concurrent transactions were not tested because neither server was available. Production checks validate configuration, not database connectivity. SQLite is used for local development and this automated suite.

SMTP delivery, complete Malayalam translations, 2FA, approved branding artwork and uploads, public registration, facilitator workflows, QR/cards, reports, Docker rollout and restoration exercises remain in their later phases. The complete platform is not claimed to be production-ready at Phase 1.

## Files created

The source inventory below excludes the virtual environment, generated database, private .env, bytecode, collected static files and QA artifacts. All are new; there were no pre-existing project files modified.

- `.env.example`
- `.gitignore`
- `DEPLOYMENT.md`
- `INSTALLATION.md`
- `README.md`
- `SECURITY.md`
- `apps/__init__.py`
- `apps/accounts/__init__.py`
- `apps/accounts/admin.py`
- `apps/accounts/api.py`
- `apps/accounts/apps.py`
- `apps/accounts/forms.py`
- `apps/accounts/management/__init__.py`
- `apps/accounts/management/commands/__init__.py`
- `apps/accounts/management/commands/create_initial_admin.py`
- `apps/accounts/management/commands/grant_role.py`
- `apps/accounts/management/commands/prune_security_records.py`
- `apps/accounts/management/commands/revoke_role.py`
- `apps/accounts/middleware.py`
- `apps/accounts/migrations/0001_initial.py`
- `apps/accounts/migrations/0002_seed_roles.py`
- `apps/accounts/migrations/0003_requestbudget.py`
- `apps/accounts/migrations/__init__.py`
- `apps/accounts/models.py`
- `apps/accounts/permissions.py`
- `apps/accounts/policies.py`
- `apps/accounts/rate_limit.py`
- `apps/accounts/security.py`
- `apps/accounts/services.py`
- `apps/accounts/signals.py`
- `apps/accounts/urls.py`
- `apps/accounts/validators.py`
- `apps/accounts/views.py`
- `apps/audit/__init__.py`
- `apps/audit/migrations/0001_initial.py`
- `apps/audit/migrations/__init__.py`
- `apps/audit/models.py`
- `apps/audit/services.py`
- `apps/audit/views.py`
- `apps/common/__init__.py`
- `apps/common/models.py`
- `apps/dashboard/__init__.py`
- `apps/dashboard/urls.py`
- `apps/dashboard/views.py`
- `apps/organization/__init__.py`
- `apps/organization/context_processors.py`
- `apps/organization/forms.py`
- `apps/organization/migrations/0001_initial.py`
- `apps/organization/migrations/0002_seed_settings.py`
- `apps/organization/migrations/__init__.py`
- `apps/organization/models.py`
- `apps/organization/services.py`
- `apps/organization/urls.py`
- `apps/organization/views.py`
- `config/__init__.py`
- `config/admin.py`
- `config/asgi.py`
- `config/settings/__init__.py`
- `config/settings/base.py`
- `config/settings/development.py`
- `config/settings/production.py`
- `config/settings/test.py`
- `config/urls.py`
- `config/wsgi.py`
- `manage.py`
- `pyproject.toml`
- `requirements.txt`
- `requirements/base.txt`
- `requirements/dev.txt`
- `requirements/lock.txt`
- `requirements/production.txt`
- `scripts/prepare_ui_check.py`
- `scripts/ui_check.cjs`
- `static/css/app.css`
- `static/img/mark.svg`
- `static/js/app.js`
- `static/vendor/README.md`
- `static/vendor/bootstrap.LICENSE`
- `static/vendor/bootstrap.min.css`
- `static/vendor/htmx.LICENSE`
- `static/vendor/htmx.min.js`
- `templates/accounts/profile.html`
- `templates/accounts/users.html`
- `templates/audit/index.html`
- `templates/base.html`
- `templates/dashboard/home.html`
- `templates/errors/400.html`
- `templates/errors/403.html`
- `templates/errors/404.html`
- `templates/errors/429.html`
- `templates/errors/500.html`
- `templates/includes/form.html`
- `templates/includes/messages.html`
- `templates/includes/pagination.html`
- `templates/organization/settings.html`
- `templates/registration/login.html`
- `templates/registration/password_form.html`
- `templates/registration/password_reset_complete.html`
- `templates/registration/password_reset_confirm.html`
- `templates/registration/password_reset_done.html`
- `templates/registration/password_reset_email.txt`
- `templates/registration/password_reset_subject.txt`
- `templates/registration/reset_confirm_fields.html`
- `tests/__init__.py`
- `tests/factories.py`
- `tests/test_admin_commands.py`
- `tests/test_auth.py`
- `tests/test_configuration.py`
- `tests/test_permissions.py`
- `tests/test_settings_audit.py`
- `PHASE1_REPORT.md`

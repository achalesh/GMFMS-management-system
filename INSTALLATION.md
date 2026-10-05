# Local installation

## Prerequisites

Python 3.12 or later. SQLite is bundled for local development. PostgreSQL is the production preference. Node.js is only needed for optional browser checks, not to run the application.

If Python is unavailable on PATH in this Codex workspace, the bundled executable used to create the existing venv was:
`C:\Users\achal\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.

## Windows / PowerShell

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
~~~

Copy that newly generated value into SECRET_KEY in your local .env. Do not paste it into a ticket or commit it. Do not overwrite an existing .env without preserving its settings.

~~~powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_kerala_locations
.\.venv\Scripts\python.exe manage.py create_initial_admin
.\.venv\Scripts\python.exe manage.py runserver
~~~

The interactive administrator command requires an email and a strong password. No administrator is created by migrations.

For this prepared workspace the venv, local .env, migrations and administrator already exist; start the server without recreating the account.

## Linux / macOS

~~~bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements/lock.txt
cp .env.example .env
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(64))"
# Put the result in .env.
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_kerala_locations
.venv/bin/python manage.py create_initial_admin
.venv/bin/python manage.py runserver
~~~

An unset development SECRET_KEY uses an ephemeral key, so sessions do not survive a restart. A persistent local .env is recommended. Production refuses an absent or insecure key.

## Database selection

Local SQLite: `DATABASE_URL=sqlite:///db.sqlite3`  
PostgreSQL: `DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/gmfms`  
MySQL/MariaDB: `DATABASE_URL=mysql://USER:PASSWORD@HOST:3306/gmfms`

The PostgreSQL driver is installed. MySQL/MariaDB additionally needs `mysqlclient>=2.2,<3` and its platform libraries. Use utf8mb4 and strict mode (configured). MySQL/MariaDB has not been exercised in this Windows environment. Run migrations and the suite against your intended server before deployment.

## Provision staff

1. Sign in with the initial administrator.
2. Visit /admin/accounts/user/add/ to create a named account. Add a unique email.
3. Grant an application role with the audited command:

~~~powershell
.\.venv\Scripts\python.exe manage.py grant_role staff_username VIEWER --actor admin_username --scope STATE
.\.venv\Scripts\python.exe manage.py grant_role district_username DISTRICT_ADMIN --actor admin_username --scope DISTRICT --district TVM
.\.venv\Scripts\python.exe manage.py grant_role block_username BLOCK_COORDINATOR --actor admin_username --scope BLOCK --district TVM --block B01001
~~~

Seed locations before assigning regional roles. TVM and B01001 are keys from the bundled master; choose the actual assigned district/block from the location screens. Unknown, inactive and mismatched codes are rejected. Legacy unresolved assignments remain denied; reconcile them with manage.py resolve_location_jurisdictions.

`is_staff` alone grants no workspace capability. An active assigned role and valid scope are required. Django superusers have full access and receive a SUPER_ADMIN role assignment automatically. The emergency admin requires is_staff plus superuser or SUPER_ADMIN authorization.

To withdraw a role, use `revoke_role` with a mandatory reason. To disable all access, deactivate the account in emergency admin. Accounts are not deleted through the admin.

~~~powershell
.\.venv\Scripts\python.exe manage.py revoke_role staff_username VIEWER --actor admin_username --reason "Assignment ended"
~~~

Django superuser status bypasses role assignment checks. Removing a SUPER_ADMIN role alone will not remove an account's is_superuser status; disable that flag or deactivate the account as appropriate.

## Email and maintenance

Development reset emails are printed to the terminal. Production uses SMTP variables and HTTPS. Never enable console email in production. Reset requests return the same confirmation for unknown and known addresses.

Run daily:
~~~powershell
.\.venv\Scripts\python.exe manage.py clearsessions
.\.venv\Scripts\python.exe manage.py prune_security_records
~~~

Login lockout is five failures per username or source IP for 15 minutes by default. After investigating, a host administrator can unlock an account using `manage.py axes_reset_username USERNAME`. At ingress, ensure source IP handling is correct; see SECURITY.md.

## Optional browser verification

Install Playwright for your local Node tooling and ensure Chrome is installed. The UI harness defaults to the installed Chrome channel; set UI_BROWSER_CHANNEL=msedge to use Edge.

~~~powershell
.\.venv\Scripts\python.exe scripts/prepare_ui_check.py
$env:DATABASE_URL='sqlite:///D:/Gramaswaraj/Web/artifacts/ui.sqlite3'
$env:MEDIA_ROOT='artifacts/ui-media'
$env:PUBLIC_BASE_URL='http://127.0.0.1:8001'
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001 --noreload
~~~

In another terminal, with Playwright resolvable by Node:
~~~powershell
node scripts/ui_check.cjs
node scripts/ui_locations_check.cjs
node scripts/ui_registration_check.cjs
.\.venv\Scripts\python.exe scripts/prepare_review_ui.py
node scripts/ui_review_check.cjs
.\.venv\Scripts\python.exe scripts/prepare_registry_ui.py
node scripts/ui_registry_check.cjs
~~~

The prep script always selects a separate database under ignored artifacts/. It generates random temporary QA credentials. It never modifies your normal database. Screenshots are written there. Stop the isolated server after checking. Adjust the absolute database path if you moved the project. Do not expose this QA server publicly.

## Location updates

See [the location import guide](data/kerala/README.md) for CSV/XLSX formats, dry runs, source provenance and reviewed updates. The seeded database is already present in this workspace. Importing does not create user accounts.

## Public registration

Open /register/media-facilitator/. Registration choices seed through migrations. See [REGISTRATION.md](REGISTRATION.md) for document requirements, upload limits, draft cleanup and receipts. The workspace administrator already exists; do not recreate it.

## Administrative review

Open /applications/ with an authorized staff account. See [REVIEW.md](REVIEW.md) for correction requests, approval, rejection and jurisdiction rules. Re-run prepare_review_ui.py before each review browser check because its approval/rejection fixtures reach terminal states. All browser decisions use the isolated QA database.

## Registry maintenance

Open /facilitators/ or /facilitators/coverage/. See REGISTRY.md for access, lifecycle actions and replacement. Schedule `manage.py expire_facilitators` daily to persist automatic expiry history; authorization and vacancies already honor expiry before that command runs. Prepare fresh synthetic registry fixtures before repeating the browser replacement workflow.

## QR verification

Open a facilitator record, then Verification link & QR. See VERIFICATION.md. After dependency installation and migrations, no extra QR service is needed. The development suite uses zxing-cpp to decode test QR images; it is listed in requirements/dev.txt and lock.txt, not production requirements.

For isolated verification browser testing, run prepare_ui_check.py, prepare_registry_ui.py, then prepare_verification_ui.py and scripts/ui_verification_check.cjs against the port-8001 QA server. Recreate fixtures before repeating suspension/token rotation.

## ID cards

Install the updated lock file and run migrations. Open a facilitator record, then ID cards & print history. See IDCARDS.md for actual-size/A4 printing, fonts, versions and revocation. Card PDFs/previews are stored inside private MEDIA_ROOT and must be backed up with the database.

# Gramaswaraj Media Facilitator Management System

**GMFMS · Kerala Grama Panchayat Association**  
Digital Media & Broadcasting Network — Gramaswaraj  
ഗ്രാമസ്വരാജ് മീഡിയ ഫെസിലിറ്റേറ്റർ മാനേജ്മെന്റ് സിസ്റ്റം

## Current delivery: Phase 10 — Deployment preparation (hosting required)

The foundation, Kerala location master and public application intake are implemented and tested. The master contains 14 districts, 152 blocks and 941 Grama Panchayats. Applicants can now submit at /register/media-facilitator/ without a staff login. Staff can review, request secure corrections, approve or reject applications at /applications/. Approval creates official facilitator IDs and appointments atomically. The facilitator registry now supports appointment history, lifecycle management, replacements, district/block coverage and vacancy detection. Public QR verification is implemented with explicit privacy controls and current authorization checks. Versioned front/back cards and print-ready PDFs are implemented. Scoped dashboards and Excel/CSV/PDF reports are implemented. Application security hardening is complete; deployment and operational acceptance remain Phase 10.

Deployment files and the [production runbook](DEPLOYMENT.md) are prepared for **gramaswaraj.in**. Hostinger shared hosting cannot run this Django application; a compatible VPS/host is required. Nothing has been published. See [Phase 10 status](PHASE10_REPORT.md).

Implemented:

- Global upload bounds, browser security headers, reset-token log redaction, expensive-operation budgets and deployment checks.
- [Security hardening audit](PHASE9_REPORT.md): 300 passing tests and dependency metadata review.

- Live state/district/block dashboards, coverage, vacancies and expiring authorization statistics.
- Nine report types, combinable filters and audited, permission-scoped Excel/CSV/PDF downloads.
- [Dashboard and report guide](REPORTS.md).

- Versioned front/back ID cards, card-size/A4 PDFs, private previews and audited reprints/revocation.
- Card-bound QR status checks and stale-card download protection.
- [ID card operation guide](IDCARDS.md).

- Scoped QR generation and public identity verification with a strict field allowlist.
- Current-status verification, consent-controlled contacts, token rotation and abuse limits.
- [QR verification guide](VERIFICATION.md).

- Searchable, scoped facilitator registry with private contact permissions and authenticated portraits.
- Appointment/status history, suspension, resignation, renewal, reactivation, transfer, role changes and atomic replacement.
- District/block coverage, permanent Panchayat profiles and effective-date vacancy detection.
- [Registry operation guide](REGISTRY.md).

- Jurisdiction-scoped application review, private document downloads and audited decisions.
- Single-use correction links with selected editable fields and resubmission history.
- Atomic approval with official IDs, primary appointment conflict checks and pending card metadata.
- [Review and approval operation guide](REVIEW.md).

- Public six-step registration with drafts, portrait cropping, private documents, skills/equipment/languages and consent.
- Unique application numbers, repeat-submit protection, private duplicate warnings and submission receipts.
- [Registration operation and configuration guide](REGISTRATION.md).

- Source-traceable Kerala location master, district/block drill-down and searchable Panchayat directory.
- Atomic CSV/XLSX imports, dry runs, audited edits and checksum-verified seed command.
- Active-location dependent dropdown APIs and foreign-key-backed geographic authorization.

- Python 3.12+, Django 5.2 LTS, Django REST Framework and server-rendered templates.
- UUID custom user model, seven seeded roles, role-specific jurisdictions and deny-by-default policies.
- Custom responsive staff dashboard, account access summary, staff list and read-only audit trail.
- Configurable English/Malayalam organization branding and conservative system/privacy defaults.
- Transactional settings changes with revision conflict detection and audit records.
- Login/logout, password change/reset, CSRF, session expiry, database-backed login and reset throttling.
- Environment-based development, test and production settings.
- PostgreSQL driver; SQLite development; MySQL/MariaDB configuration path (optional driver).
- Authenticated API identity endpoint and authenticated OpenAPI schema/documentation.
- Migrations and automatic foundation seed data, tests, local frontend assets, setup/security documentation.

No hard-coded network statistics or fabricated Panchayat master data are shown.

## Quick start

From this directory with Python 3.12+:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/lock.txt
Copy-Item .env.example .env
# Set a generated SECRET_KEY in .env; see INSTALLATION.md.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_kerala_locations
.\.venv\Scripts\python.exe manage.py create_initial_admin
.\.venv\Scripts\python.exe manage.py runserver
~~~

Open http://127.0.0.1:8000/. There are **no default credentials**. This workspace already has a virtual environment, a local ignored .env with a generated secret, and migrated SQLite tables; the administrator has been created separately. No credentials are stored in source files.

Read [INSTALLATION.md](INSTALLATION.md) for Windows/Linux commands and staff role provisioning.

## Architecture

| Package | Responsibility |
| --- | --- |
| config/settings | Environment, database, auth, API, logging and deployment configuration |
| apps/accounts | Custom users, role/jurisdiction policy, login security and provisioning |
| apps/organization | Organization and system settings, forms, transactional services |
| apps/audit | Append-only application audit events and read-only staff view |
| apps/dashboard | Staff overview, own access and public liveness endpoint |
| apps/registrations | Public intake, private files, corrections, scoped review and approval |
| apps/locations | Kerala master, imports, scoped management and public dropdown APIs |
| apps/facilitators | Identity, appointments, lifecycle/history, scoped registry, coverage and initial card metadata |
| apps/verification | Public projection, secure QR generation, token lifecycle and privacy controls |
| apps/idcards | Versioned print artifacts, authorization/source checks and card-specific verification |
| apps/common | Shared timestamp base |
| templates / static | Django templates, local Bootstrap 5, HTMX and responsive styles |
| tests | Authentication, authorization, settings, audit and configuration tests |
| scripts | Isolated browser-check fixtures and browser smoke checks |

Subsequent phases add reports, exports and deployment hardening.

## Database models

- **User** — UUID identifier, Django password hashing, email, language preference.
- **Role** — seven stable role codes seeded by migration.
- **UserRole** — active assignment, granting actor and timestamps.
- **UserJurisdiction** — scope attached to a specific role assignment.
- **State / District / Block / GramaPanchayat** — protected hierarchy, separate SEC/LSGD codes, bilingual labels and active status. Panchayat district is derived through Block.
- **Application / RegistrationDraft / RegistrationUpload** — submitted records, temporary session-owned drafts and private uploads.
- **Skill / Equipment / Language / DocumentType** — registration choice masters and document policy.
- **ApplicationSequence / DuplicateWarning** — unique numbering and private match warnings.
- **IdentityCard** — versioned issuance snapshots, private files/checksums and revocation history.
- **VerificationTokenHistory** — append-only token digest changes, actor and reason.
- **FacilitatorStatusHistory** — append-only operational decisions, actors, appointment links and old/new snapshots.
- **ReviewEvent / CorrectionRequest** — append-only review history and hashed, expiring correction grants.
- **Facilitator / FacilitatorSequence / FacilitatorAppointment / IdentityCardMetadata** — atomic approval records.
- **LocationImport** — source reference, checksum, actor and summary.
- **RequestBudget** — shared-database, expiring password-reset request counters.
- **OrganizationSetting** — one versioned branding/contact record.
- **SystemSetting** — one versioned registry/privacy policy record.
- **AuditLog** — actor, action, entity, old/new values, reason and timestamp.

Django and django-axes add their own session, permission and login-security tables.

Jurisdictions now reference District/Block records. Legacy codes resolve exactly during seeding or with resolve_location_jurisdictions; unknown, mismatched or inactive locations grant no regional access. See [data provenance and import guide](data/kerala/README.md).

Every subsequent administrative data endpoint must call both the capability policy and `scope_queryset()` (or a scoped object check). A role without a jurisdiction grants no access. A statewide VIEWER assignment cannot widen a DISTRICT_ADMIN assignment's write scope. Reviewer defaults exclude approval; ID card operators cannot approve.

## Routes

| Route | Access |
| --- | --- |
| / | Assigned staff dashboard |
| /register/media-facilitator/ | Public application, no staff login |
| /register/media-facilitator/confirmation/ | Originating session receipt |
| /verify/<token>/ and /api/v1/verify/<token>/ | Public allowlisted verification |
| /verification/<uuid>/ | Scoped QR preview, download and authorized token replacement |
| /cards/<facilitator>/ | Scoped card versions, generation, download/reprint and revocation |
| /facilitators/ | Scoped registry search and filters |
| /facilitators/<uuid>/ | Identity, appointments and authorized management actions |
| /facilitators/coverage/ | Scoped district/block coverage and vacancies |
| /facilitators/panchayats/<id>/ | Permanent institutional appointment history |
| /applications/ | Jurisdiction-scoped reviewers and administrators |
| /applications/<uuid>/ | Scoped review, documents and authorized decisions |
| /correct/<uuid>/ | Valid correction-link holder; selected fields only |
| /admin/registrations/application/ | Super-admin read-only intake inspection |
| /profile/ | Authenticated user's own access |
| /accounts/login/ | Public, throttled |
| /accounts/logout/ | POST with CSRF |
| /accounts/password/change/ | Authenticated |
| /accounts/password/reset/ | Public, throttled reset request |
| /accounts/password/reset/sent/ | Generic confirmation |
| /accounts/password/reset/<uid>/<token>/ | Single-use token |
| /accounts/password/reset/complete/ | Reset completion |
| /accounts/users/ | Account managers |
| /settings/organization/ | State/super administrators |
| /settings/system/ | Super administrators |
| /audit/ | State/super administrators |
| /admin/ | Emergency super-administrator access; is_staff also required |
| /locations/ | Scoped staff location master |
| /locations/panchayats/ | Scoped searchable directory |
| /locations/import/ and /locations/edit/... | Super administrators |
| /api/v1/districts/ | Public active district labels/codes |
| /api/v1/blocks/?district=ID | Public active blocks in selected district |
| /api/v1/panchayats/?block=ID | Public active Panchayats in selected block |
| /api/v1/auth/me/ | Assigned staff, minimal own identity |
| /api/schema/ and /api/docs/ | Assigned staff |
| /i18n/setlang/ | POST language preference |
| /health/ | Public liveness only; no configuration details |

## Validation

~~~powershell
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test --settings=config.settings.test
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
~~~

Tests use an isolated database. SQLite tests do not prove PostgreSQL/MySQL concurrency behavior. Approval/sequence/appointment concurrency tests must also run on the intended production engine. See [PHASE7_REPORT.md](PHASE7_REPORT.md) for the current validation record and [PHASE1_REPORT.md](PHASE1_REPORT.md) for the historical foundation delivery.

## Production and remaining decisions

[DEPLOYMENT.md](DEPLOYMENT.md) covers the production configuration baseline; [SECURITY.md](SECURITY.md) documents boundaries. Docker packaging, full production rollout and restoration exercises are Phase 10.

The bundled master has source URLs/checksums and a documented older hierarchy reference; review official boundary updates before production rollout. Approved logo artwork, final signatory, SMTP provider, public hostname and production database credentials can be supplied in their relevant phases. No credentials or approval decisions have been invented.

The initial staff UI is English with Unicode Malayalam branding, Django locale middleware and a language switcher. Complete translated catalogs remain future work. The public registration form supports Malayalam names and safely handles private photo/document uploads.

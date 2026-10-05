# Phase 5 — Facilitator Registry

## Delivered

- Scoped registry search by official ID, name/Malayalam name, permitted mobile, application number and location; combinable status, role, geography, registration, approval and expiry filters.
- Identity detail with authenticated portrait, permission-filtered contacts, current appointment and permanent appointment history.
- Atomic lifecycle services: suspend, inactivate, resign, revoke, reactivate, renew, transfer, role change, current appointment reference/notes and replacement.
- Replacement approves a reviewed incoming application and retires the outgoing primary identity in one transaction; retained IDs/tokens/history and failed-operation rollback.
- Distinct-Panchayat coverage, district/block views, vacancy filter and institutional profiles with scoped applications/history.
- Effective expiry independent of maintenance; idempotent expire_facilitators command records expiry history.
- PRIMARY/ASSISTANT/ADDITIONAL selection on approval, with the primary conflict policy maintained.

## Models and migrations

Facilitator adds revision and current_appointment. FacilitatorAppointment adds ended_at, end_reason, approved_at, appointment_reference and private notes. New append-only FacilitatorStatusHistory holds actor, action, previous/new status, reason, appointment and old/new snapshots. Migrations 0002–0005 preserve existing identities, attach existing appointments and retain original approval times.

## Files and routes

Added apps/facilitators/{selectors,services,forms,views,urls}.py, lifecycle migrations, management/commands/expire_facilitators.py, templates/facilitators/, static/css/registry.css, tests/test_registry.py, scripts/prepare_registry_ui.py, scripts/ui_registry_check.cjs and REGISTRY.md.

Updated approval forms/services, application navigation, location detail links, dashboard readiness and setup/security/operation documentation.

Routes: /facilitators/, /facilitators/<uuid>/, /facilitators/<uuid>/portrait/, /facilitators/<uuid>/actions/<action>/, /facilitators/coverage/, district/block coverage subroutes and /facilitators/panchayats/<id>/.

## Validation

206 automated tests: 34 new registry tests and 172 earlier-phase tests. Coverage includes current appointment/history initialization, lifecycle state/revision checks, transfer scope, role/primary conflicts, replacement validation and rollback, expiry/renewal, append-only history, CSRF, contact search privacy, portrait scope, institutional history and page rendering.

Browser QA exercises search, private portrait, suspension/reactivation, renewal, transfer, replacement, vacancy/history and responsive layouts at desktop, 768, 390 and 360 pixels. Browser fixtures use artifacts/ui.sqlite3 and artifacts/ui-media exclusively. Screenshots are inspected for desktop/mobile layout.

Final checks include migrations/drift, Django checks, lint/format, dependency consistency, API schema validation, static collection and production-settings checks. Production PostgreSQL/MySQL concurrency is not verified by local SQLite tests.

## Decisions and boundaries

Transfers preserve the original facilitator ID (including its original district code) and token. Revoked/replaced identities are terminal; resignation can be followed by a new appointment after validity/conflict checks. Assistant/additional roles do not occupy a primary vacancy. All changes are immediate and require a reason.

No real application was approved, replaced or altered by implementation. Existing administrator and location records are preserved. QR public verification is Phase 6; rendering/versioning cards is Phase 7; reports/exports are Phase 8. Pending card metadata remains its original approval snapshot.

Run locally: `.\.venv\Scripts\python.exe manage.py migrate`, then `.\.venv\Scripts\python.exe manage.py runserver`. See REGISTRY.md for maintenance and workflows.

The workspace has no Git repository, so no commit was created.

Final local verification: the restarted app responds successfully; the existing active administrator, 14 districts, 152 blocks, 941 Panchayats and one submitted application remain. There are no real approved facilitator identities yet. Existing review and location browser regression checks also passed. All final configuration/lint/schema/dependency/static checks listed above passed.

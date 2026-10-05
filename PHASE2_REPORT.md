# Phase 2 delivery — Kerala Location Master

## Delivered

- State, District, Block and GramaPanchayat models with protected parent references, unique codes, English/Malayalam fields, activation flags and revision-controlled edits.
- Bundled source-traceable Kerala snapshot: 14 districts, 152 blocks, 941 Grama Panchayats. Loaded into the local application database.
- Atomic CSV/XLSX importer, dry-run mode, explicit update option, import history and audit events. Checksum-verified seed command.
- Public read-only dependent dropdown APIs: /api/v1/districts/, /api/v1/blocks/?district=ID and /api/v1/panchayats/?block=ID. Active ancestors required; contacts excluded; pagination and throttling enabled.
- Responsive location overview, district/block drill-down, searchable Panchayat directory, profiles, edit forms and import screen.
- District/block foreign keys on role jurisdictions; exact legacy reconciliation and fail-closed behavior for unknown, mismatched or inactive locations.
- Server-enforced district/block access boundaries and SUPER_ADMIN-only master mutation.

## Files

New application: apps/locations/ (models, migration, selectors, forms, services, importer, API, views, URLs and seed/import commands).
New data: data/kerala/ (CSV, source manifest, reviewed crosswalks and provenance README).
New UI: templates/locations/ and static/js/locations.js.
New tests/tooling: tests/test_locations.py, scripts/ui_locations_check.cjs and source preparation scripts.
Updated integration: accounts models/migration/policies/services/reconciliation command, dashboard, settings/URLs, navigation/styles, test factories, dependency lock and installation/security/deployment documentation.

## Validation

92 automated tests pass, including 32 location tests. They cover complete snapshot counts by district, idempotent seeding, hierarchy protection, import rollback, audit failure rollback, dry runs, malformed CSV/XLSX, formula rejection, explicit updates, access boundaries, inactive ancestors, legacy reconciliation, CSRF and API pagination.

Migration drift, Django system checks, OpenAPI schema validation, Ruff and static asset collection all pass. Production configuration checks also report no issues; they do not connect to or validate a production database. Browser validation covers location drill-down, dependent filtering, an audited edit and dry-run import against an isolated QA database, with 1440, 768, 390 and 360 pixel layouts and no JavaScript errors. Desktop and mobile screenshots were visually inspected.

## Decisions and limits

The Panchayat district is derived through Block rather than duplicated in storage. SEC codes and LSGD codes are kept separately. Official codes and parent relationships cannot be edited casually; boundary changes require a reviewed migration.

Only verified values are seeded. Block/Panchayat Malayalam names and institutional contacts are blank where unavailable. The directories were retrieved on 28 September 2026, but explicit hierarchy verification uses the 2015 LSGD reference. See data/kerala/README.md for provenance and refresh requirements.

SQLite validation does not establish PostgreSQL/MySQL concurrency behavior. Those engines, SMTP, hosting and production rollout remain unverified. No facilitator registration, approvals, identities or cards are implemented by Phase 2. Phase 3 has not started.

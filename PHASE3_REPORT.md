# Phase 3 — Public Registration

## Delivered

Public route: /register/media-facilitator/.

- Six server-validated steps: location, personal details, professional experience/skills/languages, equipment/social profiles, photo/documents, review/consent.
- Database-driven dependent location selections with active-parent validation and a no-JavaScript fallback.
- Session-owned drafts, revision conflict checks, back/edit navigation, expiry and a draft cleanup command.
- Indian mobile/PIN validation, WhatsApp default, optional private emergency contacts, URL/date validation.
- Database choice masters and configurable document requirements.
- JPG/PNG photo cropping, compressed portrait derivatives and private PDF/image uploads with randomized names, stream/size limits and content checks.
- Required accuracy/processing consent and independent optional public-contact consents, with version/text/timestamp snapshots.
- Transactional application-number allocation, repeat-submission idempotency, SUBMITTED status and a private confirmation receipt.
- Private duplicate warnings for existing application contacts, Panchayats and similar names. Read-only emergency-admin inspection.
- CSRF, rate limits, honeypot/minimum completion time, no-store responses and cleanup on failed/replaced uploads.

## Files and setup

New apps/registrations/ contains models, three migrations, forms, services, upload validation/handler, public views/URLs, read-only admin and management commands.
New templates/registrations/, static/css/registration.css and static/js/registration.js provide the public UI.
New tests/test_registrations.py and scripts/ui_registration_check.cjs validate the flow.
Updated settings, routing, login/dashboard links, private-response middleware, dependency lock and documentation integrate it with Phases 1–2.

Migrations are applied to the local database. Registration choices seed automatically. The existing administrator and 14/152/941 location master are preserved. Browser-created sample applications are isolated in the QA database.

## Validation

129 automated tests pass (37 registration tests plus 92 previous-phase tests). Coverage includes hierarchy forgery, malformed files and PDFs, consent/policy changes, expired/stale drafts, rate limits, CSRF, private session access, audit/file rollback, replacement/removal cleanup, duplicate warnings, application numbering and repeat submission.

The browser check completes an anonymous application with live location dropdowns, photo cropping, PDF upload, review and consent. It checks receipt isolation, no sensitive contact data in the receipt, no JavaScript errors and 1440/768/390/360 layouts. Desktop landing, mobile upload and receipt screenshots are visually reviewed.

Ruff, migration-drift checks, Django checks, dependency checks, OpenAPI validation, static collection and production configuration checks all pass. Production configuration checks report no issues but do not establish production database or hosting readiness. PostgreSQL/MySQL concurrency and actual production hosting are not validated by local SQLite tests.

## Decisions and boundaries

Photo is required; document requirements are configurable and initially optional. Optional personal fields remain optional to minimize collection. No IP/user-agent is stored as consent evidence; rate budgets retain only a keyed digest and short-lived counters.

PDF parsing/content rejection is not malware scanning. Files remain private; staff downloads and review actions belong to Phase 4. No emails, cross-device recovery, public tracking, approval, facilitator identity, appointment or QR are created. Existing active-facilitator duplicate checking awaits Phase 5.

Phase 4 has not started. See REGISTRATION.md for operation, data retention and configuration.

# Phase 6 — QR Verification

## Delivered

- Secure public verification using existing cryptographic random approval tokens.
- Staff QR preview/download with the configured public origin and object-level authorization.
- Anonymous mobile verification page, sanitized portrait endpoint and matching allowlisted JSON endpoint.
- Explicit active/inactive/suspended/expired/revoked/replaced states, effective-date checks and inactive-location handling.
- Consent plus policy checks for optional contacts/social links; no private documents, notes or administrative data in public responses.
- Atomic, reasoned, revision-checked token replacement with old-link invalidation and append-only digest history.
- Shared-IP lookup/portrait budgets, no-store/no-referrer/noindex/CSP headers, sanitized failures and token-path log redaction.

## Files and model

Added apps/verification/{models,projection,services,views,urls,staff_urls,logging}.py and its initial migration. VerificationTokenHistory records facilitator, prior/replacement digests, actor, timestamp and reason.

Added templates/verification/, static/css/verification.css, static/css/verification-staff.css, tests/test_verification.py, scripts/prepare_verification_ui.py, scripts/ui_verification_check.cjs and VERIFICATION.md.

Updated config routing/installed apps/logging, registry QR link access, organization policy help, navigation/footer, dashboard phase label, requirements and operating/security/deployment documentation. Production adds qrcode; development adds zxing-cpp for independent QR decoding. requirements/lock.txt records the tested versions.

## Routes

Public: /verify/<token>/, /verify/<token>/portrait/, /api/v1/verify/<token>/.
Staff: /verification/<uuid>/, /verification/<uuid>/qr.png, /verification/<uuid>/rotate/.

## Validation

238 automated tests: 32 new verification tests and 206 earlier-phase tests. Coverage includes exact public fields, private-field exclusion for anonymous/authenticated requests, publication consent, unsafe URL handling, authorization/date/location states, portrait privacy, invalid tokens, rate limits, safe failures, role scopes, token rotation/rollback/CSRF, history protection and log redaction.

Independent QR decoding verifies the encoded URL from both an automated generated image and the browser-downloaded PNG. Browser checks cover anonymous public HTML/JSON, portrait, QR download, live suspension, token replacement and old-link denial at desktop/tablet/mobile widths (1440/768/390/360). Public active/suspended layouts are visually inspected. Synthetic fixtures and screenshots use isolated artifacts storage, never real applicant records.

Final verification includes migrations/drift, system and production-settings checks, formatting/lint, dependency consistency, static collection and API schema validation.

## Remaining boundaries

No public listing/search directory is introduced. Production hostname/HTTPS, proxy logging redaction, ingress/cache rules and production database concurrency must be validated on deployment. Localhost QR codes cannot be verified from other devices. ID cards are Phase 7; reporting/exports are Phase 8.

No real applicant approval, suspension or token replacement is performed during implementation. Existing account/location/application data remain preserved. The directory is not a Git repository, so no commit is created.

Run locally with `.\.venv\Scripts\python.exe manage.py migrate` and `.\.venv\Scripts\python.exe manage.py runserver`. See VERIFICATION.md for the public response contract and operation guide.

Final local verification passed after restarting port 8000. Existing data remains: one active administrator, 14 districts, 152 blocks, 941 Panchayats, one application and zero approved facilitator identities. No real approval or token change was performed. All final checks listed above passed; production database execution remains unverified.

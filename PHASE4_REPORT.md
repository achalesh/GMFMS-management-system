# Phase 4 — Administration & Approval

## Delivered

- Scoped application inbox, status counts, combined search/location/date filters and pagination.
- Review detail showing personal/professional data, documents, consent, current duplicate warnings and append-only history.
- Audited private file downloads and authorized sanitized-portrait previews.
- Start review, request/renew/cancel correction, approve and reject actions with server-side capability, status and revision checks.
- Forty-eight-hour correction links, hashed secrets, session exchange, field allowlists, consent reconfirmation, file replacement, change history and one-use resubmission.
- Atomic approval creating a unique district-sequenced facilitator number, a primary appointment, verification-token record and initial pending card metadata.
- Active-primary conflict protection under the configured business rule and duplicate acknowledgement before approval.
- Responsive staff screens and public correction screens.

## Scope decision

The master specification requires identity, appointment and initial card metadata to be created atomically on approval. Therefore Phase 4 includes those minimum supporting models in apps/facilitators. Broader registry screens, operational status/replacement workflows, public QR verification and card generation are not implemented ahead of their phases.

## Files

New registrations modules: review_selectors.py, duplicates.py, review_forms.py, review_services.py, review_views.py, review_urls.py, application_data.py, correction_forms.py, correction_services.py, correction_views.py and correction_urls.py.
Updated registrations models/migrations add revision/decision fields, ReviewEvent and CorrectionRequest.
New apps/facilitators/ models/migration implement the minimum approval records and district sequence.
New templates/applications/, templates/corrections/, static/css/review.css and static/js/correction-access.js.
Updated shared form markup fixes checkbox groups using fieldsets instead of single-checkbox layout.
Updated navigation, dashboard, routing, cache policy and upload stream bounds.
New tests/test_review.py, scripts/prepare_review_ui.py, scripts/ui_review_check.cjs and REVIEW.md.

## Validation

172 automated tests pass: 42 new review/correction tests, one block-page regression test and 129 previous-phase tests. They cover jurisdiction and role boundaries, hidden cross-scope matches, revision conflicts, state transitions, atomic identity/sequence rollback, configured primary conflicts, correction allowlists, expired/revoked/used tokens, CSRF, audit history protection and private files.

Browser validation exercises staff login, inbox/search, private download, review and approval, generated official ID, applicant correction access and document replacement, link reuse denial and rejection, including desktop/tablet/mobile layouts. Validation results and screenshots are generated only in the isolated QA database/media directory.

Code formatting/lint, migration drift, Django checks, API schema and production-configuration checks are included in final verification.

## Limits and next phase

No real application has been approved or rejected as part of implementation; browser decisions use explicit QA fixtures. Existing administrator and location data remain preserved.

Correction links are displayed for authorized staff to share manually; no external messages are sent. Tokens expire in 48 hours and old links are revoked on renewal/cancellation. Production hostname/HTTPS and operational policies still require deployment configuration.

Production PostgreSQL/MySQL concurrency has not been exercised in this local environment. SQLite tests establish application behavior, not production locking guarantees. Public QR endpoints, rendered cards and broader registry/lifecycle work remain pending.

See REVIEW.md for workflow, access matrix, business rules and operational guidance.

Final verification also passed dependency checks, static collection and the existing six-step registration browser flow. Desktop and mobile review/correction screenshots were visually inspected. An existing block-detail template variable collision was corrected and covered by a regression test. The local app was restarted; the existing administrator, all 1,107 location records and the existing submitted application were preserved.

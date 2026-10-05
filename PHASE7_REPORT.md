# Phase 7 — ID Cards

## Delivered

- Front/back identity cards with portraits, organization branding, appointments, validity, verification QR, issue/version details, signatory area and organizational terms/contact.
- Two-page card-size (85.6 × 54 mm) PDF and two-page A4 PDF with crop marks; authenticated PNG previews from actual PDF pages.
- New immutable-by-workflow version records, generation and reprint audit events, supersession and reasoned revocation with actor/timestamps.
- Current authorization/source checks, revision conflict checks, file checksums and rollback cleanup; stale cards cannot be downloaded/reprinted.
- Card-bound public QR verification distinguishes an invalid printed version from an otherwise active identity.
- Embedded Malayalam font and HarfBuzz shaping; validation rejects unsupported characters/overflow rather than silently losing text.

## Files, models and routes

Added apps/idcards/{models,services,rendering,views,urls,public}.py and initial migration; templates/idcards/, static/css/cards.css, licensed static/fonts/NotoSansMalayalam-Regular.ttf, tests/test_idcards.py, scripts/ui_cards_check.cjs, scripts/check_card_artifacts.py and IDCARDS.md.

IdentityCard stores version/card number, facilitator/appointment, issue/expiry dates, actor/timestamps, status/revocation, random public token, source digest/snapshot and private PDF/preview assets with PDF hashes.

Routes: /cards/<facilitator>/, generate/, <card>/, <card>/preview/front|back/, and <card>/actions/download|revoke/. Existing /verify/<token>/ and public JSON accept the optional random card query token. QR-only identity verification remains supported.

Updated registry links, verification projection/templates/log redaction, configuration, dependencies/lock and operation/security/deployment documentation.

## Validation

256 automated tests: 18 new card tests plus 238 previous-phase tests. Tests verify dimensions, both QR codes, PDF text privacy, A4 layout metadata, version preservation, role/jurisdiction/CSRF boundaries, required reasons/revisions, checksum failures, rollback/file cleanup, expiry/stale blocking, token binding, card-vs-identity revocation, and Malayalam rendering.

Browser checks passed generation, real PDF front/back previews, both downloads, supersession/revocation, 1440/768/390/360 responsive layouts and no JavaScript errors. Independent decoder checks succeeded for both sides of both downloaded PDF formats and resolved to superseded public-card warnings as expected.

Poppler rendered both formats for visual inspection. The front/back layout, card placement/crop marks, text and QR readability were inspected; a separate Malayalam rendering was also inspected. The bundled Poppler reported missing optional display-font mappings for Symbol/ArialUnicode; the embedded card fonts rendered correctly. Physical printer/duplex acceptance remains a deployment check.

Final validation on 2026-10-04 passed: 256 tests, migrations/drift, Django checks, lint/format, dependency consistency, static collection, schema validation, and a fresh isolated browser/PDF-decoder run. Production-settings checks could not complete: Windows Application Control blocked the psycopg binary DLL and no system libpq was available. Repeat the production check on the deployment host with its PostgreSQL driver installed and permitted.

## Boundaries

Only synthetic QA identities received cards. The real administrator, location master and submitted application remain unchanged. Card operators may issue/reprint; management permission is required for revocation. All official deployment branding/signatory/public-hostname choices remain configurable. No forged signature/stamp is generated. Public profiles with card state expose no private administrative fields.

Production database concurrency and physical printing are not verified by local tests. Reports/exports remain Phase 8. The workspace has no Git repository, so no commit is created.

Start locally with `.\.venv\Scripts\python.exe manage.py migrate` and `.\.venv\Scripts\python.exe manage.py runserver`. See IDCARDS.md for workflows and print instructions.

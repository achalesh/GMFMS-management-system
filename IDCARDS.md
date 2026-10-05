# ID card generation and history

Open a facilitator record, then **ID cards & print history**. Only scoped administrators and ID_CARD_OPERATOR assignments have card access. Administrators with facilitator-management permission may revoke cards; card operators can generate/download/reprint but cannot revoke unless separately authorized.

## Issuance

Generation requires an approved, currently active identity and appointment, active locations, current validity, a verified private portrait, current revision and a reason. Check organization branding, public HTTPS origin and signatory settings before printing. A new version supersedes older issued versions atomically. Failed rendering, storage or audit operations roll back database changes and clean newly saved files; a process crash or commit/storage failure can still leave orphaned files for operational reconciliation.

Each IdentityCard retains a unique card number/version, issue/expiry dates, generation actor/time, appointment, printable snapshot, source fingerprint, random public card token, PDF checksums and private PDF/preview files. Revocation retains actor/time/reason. Generated versions are not overwritten or deleted through the application. The initial approval metadata is marked ISSUED after generation; the actual version record and current-state checks are authoritative.

The source fingerprint covers printed identity/appointment/location/organization data, portrait checksum, QR origin and identity token. Transfers, renewal, token rotation or changes to printed information make existing cards outdated. Suspension, expiry and inactive hierarchy block printing. Status changes need not delete historical artifacts.

## PDFs and layout

Two downloadable formats use the same front/back design:

- Card size: two pages, each 85.6 × 54 mm.
- A4: two pages with centered front/back cards and crop marks, retaining exact card dimensions.

Print at **100% / Actual size**, not Fit to page. Test duplex orientation and crop alignment on the intended printer before a batch. Digital dimensions, renderings and scan readability are tested; no physical printer acceptance is claimed.

Front: existing G branding mark, organization name, portrait, full name, role, official ID, Panchayat, district, validity and card-bound QR. Back: block/district, issue date/version, verification instructions, QR, terms, configured organization phone and signatory area. The application does not invent a signature or stamp. Personal phone, address, DOB, emergency contact and private documents are never printed.

English/Latin uses embedded Vera; Malayalam uses bundled Noto Sans Malayalam with HarfBuzz shaping. Font source, license and checksum are in static/fonts/README.md. ID_CARD_FONT_PATH can override the base font. Unsupported glyphs or text that cannot fit fail with a validation message instead of producing clipped or missing text. Review the preview before printing.

## Downloads, reprints and revocation

Every download/reprint requires POST, CSRF, a current revision and reason, and records an audit event. Choose card-size or A4 output. Checksums are verified before returning a private attachment. GET never generates a new card or records a reprint. Previews are authenticated images derived from the stored PDF; they are disabled for non-current cards. Historical metadata and the scoped generation/reprint/revocation log remain available.

Revoking a card does not revoke the facilitator identity. The printed QR includes the ordinary identity verification URL plus a random `card` query token. Scanning checks both current identity authorization and that specific card version. REVOKED, SUPERSEDED, OUTDATED, EXPIRED and INACTIVE cards show explicit warnings and never display optional contact details. Unknown/mismatched card tokens return generic 404. Scanning an ordinary identity QR without a card parameter verifies only the identity, not any particular piece of printed plastic/paper.

Public responses with a valid card parameter add only card number, version, status, issue date and expiry. If invalidated, identity_status preserves the independent identity state while is_authorized becomes false for the presented card. Internal snapshots, file locations, UUIDs, checksums and reasons remain private.

## Deployment and maintenance

Install updated requirements and run migrations. ReportLab creates PDFs; PDFium creates PNG previews; qrcode supplies QR images; uharfbuzz shapes Malayalam. Store private_media on persistent restricted storage and back it up with the database. Never create a public media alias. Do not cache card/verification routes at a proxy. Redact both verification path tokens and the card query parameter in ingress/access logs.

Production row-lock/concurrency behavior must be exercised on PostgreSQL/MySQL. Font/template changes should bump the renderer source template version when they require invalidating previously generated cards. Existing card PDFs remain their original issuance snapshots; they are never regenerated silently.

For isolated QA: prepare_ui_check.py, prepare_registry_ui.py, start the QA server with artifacts/ui.sqlite3, artifacts/ui-media and PUBLIC_BASE_URL=http://127.0.0.1:8001, then run scripts/ui_cards_check.cjs. It creates two synthetic versions, downloads both PDF formats and revokes the second. scripts/check_card_artifacts.py decodes both downloaded PDFs, checks superseded scan responses and produces a Malayalam visual proof. QA artifacts are not official cards.

Security budget: at most 30 card-generation POST attempts per hour per account. A 429 response includes Retry-After.

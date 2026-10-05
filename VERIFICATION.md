# QR identity verification

## Staff workflow

Approve an application, open its facilitator registry record, then choose **Verification link & QR**. Scoped administrators and ID card operators can preview/download the PNG and open the public verification page. Reviewers/viewers without card or management permission cannot retrieve the staff QR screen.

The QR contains only the verification URL generated from PUBLIC_BASE_URL. It never embeds names, contacts, dates of birth, UUIDs or document information. Existing random 32-byte URL-safe tokens issued at approval are reused. PNGs use black modules, a four-module quiet zone and medium error correction. They are generated from current state rather than stored as stale artifacts.

Local QR links work only on this computer. Set PUBLIC_BASE_URL to the actual HTTPS origin before printing or sharing production codes. Request Host headers do not determine the encoded address. Token publication does not provide a browsable/searchable public directory.

## Public routes and response contract

- /verify/<token>/ — mobile-friendly anonymous verification.
- /verify/<token>/portrait/ — sanitized JPEG portrait only.
- /api/v1/verify/<token>/ — anonymous GET/HEAD JSON representation of the same public projection.

The JSON contract has name, name_ml, facilitator_id (the official display ID), role, panchayat, block, district, status, status_label, is_authorized, valid_until, updated_at (record date), portrait_url and organization. Organization exposes only name, short_name and network_name. The JSON route is a plain Django endpoint documented here; it is not automatically included in the DRF-generated OpenAPI schema.

Only active authorization may additionally expose mobile, email or social_profiles. Each requires both the corresponding System & privacy policy switch and that applicant's separate opt-in. Turning either off removes the field on the next request. Social profiles use an explicit key list and validated HTTP(S) URLs; credential-bearing and unsafe URLs are rejected. Optional contacts are suppressed for every non-active status.

Never exposed: internal UUIDs, application number, DOB, gender, home address, PIN, emergency contacts, equipment, uploaded documents, internal notes, review reasons, consent metadata, raw scan IP or token-history digests. Public HTML receives only this restricted dictionary, never a facilitator/application model or staff context. Authenticated staff using the public URL receive the same restricted response.

## Authorization states

ACTIVE requires an approved originating application, matching current appointment, active person and appointment, current effective dates, unexpired validity and active location ancestry. Expiry takes effect after the inclusive valid-until date even before maintenance runs. The displayed expiry is the earlier of identity and appointment expiry.

SUSPENDED, INACTIVE, EXPIRED, REVOKED and REPLACED show explicit non-active warnings. Future/ended appointments, inactive location ancestors, missing appointments and unknown states fail closed. Transfer updates location while retaining the existing QR. Replacement preserves the outgoing token, which now reports REPLACED; the incoming identity receives its own token.

Invalid and deliberately rotated tokens return a generic 404 with no identity data. Processing/storage failures return generic 503 responses without debug traces, even in local debug mode.

## Token replacement

From the QR screen, registry managers can replace the verification token with a mandatory reason, current revision and explicit acknowledgment. Old QR codes and links stop working immediately; identity and appointment history remain. New printed cards must use the new QR.

Token replacement is atomic with audit and append-only VerificationTokenHistory records. History stores SHA-256 digests of old/new tokens, never plaintext. Ordinary status changes do not rotate tokens. A stale request or audit failure does not partially replace a token. Card operators cannot rotate unless separately granted scoped management permission.

## Privacy, abuse controls and deployment

Public pages, portraits and JSON use private/no-store cache controls, no-referrer, noindex/nofollow/noarchive, nosniff and a restrictive content security policy. Assets are local; no third-party analytics, external fonts or embedded social content are loaded.

A shared database budget permits 120 page/JSON requests per source IP/hour and 240 portrait requests/hour, including invalid-token attempts. Limits return 429 with Retry-After. Counters use keyed IP digests and existing security-record pruning. Fixed windows allow adjacent-window bursts; users behind a shared IP share limits. Reverse proxies must supply a trustworthy source IP according to SECURITY.md. No per-person scan tracking/audit is collected.

Django server/request messages redact verification token path segments. Configure equivalent path redaction or disable token-bearing access URLs at Nginx, Gunicorn, CDN and monitoring layers; application filters cannot control external logs. Do not cache verification results at the proxy or CDN. Rotate compromised tokens and regenerate affected cards when the card phase is available.

public_directory_enabled remains a future public-browsing policy and does not gate token verification. Deployment, rate/concurrency acceptance and retention remain operational work.

## Verification tooling

Production uses qrcode/Pillow. Development tests additionally use zxing-cpp to decode the generated PNG back to its exact URL. Tests cover the public field allowlist, consent/policy combinations, status states, stale tokens, CSRF, role/scope boundaries, rollback, logging and rate limits.

For isolated browser QA: run prepare_ui_check.py, prepare_registry_ui.py and prepare_verification_ui.py; run the QA server on port 8001 with artifacts/ui.sqlite3, artifacts/ui-media and PUBLIC_BASE_URL=http://127.0.0.1:8001; run scripts/ui_verification_check.cjs. The harness suspends and rotates only its synthetic fixture. Create fresh fixtures before repeating it.

## Printed card verification (Phase 7)

Printed PDFs use the identity URL plus a random `card` parameter. Both identity and card state are validated. Card revocation/supersession/changed printed data disable that card even when the identity remains active. Public JSON adds the limited card fields documented in IDCARDS.md; requests without the card parameter keep the original identity-only contract. Logs must redact the card parameter as well as the identity path token.

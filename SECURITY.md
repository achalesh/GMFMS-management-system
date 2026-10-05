# Security boundaries — Phases 1–9

## Authentication and access

Django owns password hashes, CSRF, reset tokens and sessions. Passwords have a 12-character minimum plus similarity, common-password, numeric-only and repeated-pattern checks. Sessions expire after 1,800 seconds by default and on browser close. Password resets expire after one hour. Security-sensitive forms use Django's sensitive-parameter protections.

django-axes keeps failed-attempt counters in the database, shared across workers. Five failures lock the username OR the source IP for 15 minutes. Password-reset requests use atomic database counters with a five-request/15-minute fixed window per source IP. A window boundary can permit two adjacent budgets. Rate limits are abuse mitigation, not a substitute for ingress controls.

Roles are application capabilities rather than Django group permissions. Every role assignment owns its scope. Restricted roles never become statewide through an unrelated viewer assignment. Unknown capabilities, inactive users, missing scopes and malformed role/scope combinations fail closed.

The scope-free dashboard check permits entry only. It must never be used as authority for an individual record. All future record queries must be scoped on the server, including exports, API lists, counts and document downloads.

## Geography phase boundary

Regional scopes reference exact District/Block foreign keys and validate their active ancestor chain on every policy check. Unknown, unresolved, contradictory or inactive scopes grant no regional access. Master data edits/imports require SUPER_ADMIN; staff lists, searches, counts and detail pages are jurisdiction-filtered. Public dropdown APIs deliberately expose only active institution labels, codes and parent IDs, never contacts.

Imports are bounded to 5 MB/5,000 rows; XLSX expanded ZIP size is capped and formulas are rejected. All rows, import history and audit events share one transaction. Dry runs roll back without emitting a successful import audit event. Codes/parent relationships are protected at the model/service boundary; raw SQL or arbitrary ORM updates are trusted maintenance, not a supported administrative interface. Reorganization requires a reviewed migration.

Import batches serialize on the organization singleton lock and edits lock their rows on databases supporting select_for_update. SQLite cannot validate those concurrency guarantees; test the target production engine.

## Privacy

The own-identity API explicitly serializes only username, display name and language preference. Public verification uses a separate explicit projection; see VERIFICATION.md. No generic private-media URL is served, even in development; the public verification portrait route serves only the sanitized approved portrait by token. Optional public contact policies default off; optional contact publication additionally requires applicant consent. Always-private fields are absent from configurable public policy.

All authenticated responses and authentication/API responses use private/no-store cache controls. Passwords, request bodies, email reset tokens and raw credentials are not written to application/security log messages. Development console email intentionally prints reset links; restrict terminal access and use SMTP in production.

Audit actor IDs and login-attempt metadata are security records. Set a retention policy before rollout. Audit IP addresses are not populated by default; login throttling needs source IP metadata. Do not enable invasive collection without a concrete operational need.

## Audit limitations

Location, settings and permission services record changes atomically with their audit event. Password changes/resets and login/logout are recorded; failed logins are counted by axes and recorded as generic security events. Emergency account edits record security-flag changes.

Audit model/queryset update/delete operations are blocked, including reconstructed-instance overwrites. Normal administrators have no audit edit route. This is application-level append-only protection, **not tamper-proof storage against database owners or arbitrary shell/SQL access**. Before rollout, use a runtime DB role with INSERT/SELECT only on the audit table, a separate migration owner, and external append-only log retention. These operational permissions must be tested on the chosen database.

## Production environment

Production settings fail without a strong secret, explicit hosts, HTTPS public URL and PostgreSQL/MySQL. Secure cookies, SSL redirect, HSTS, nosniff and frame denial are enabled. Deployment hosts must use HTTPS before enabling this profile.

Forwarded headers are untrusted by default. Enable TRUST_PROXY_SSL_HEADER only when a trusted reverse proxy overwrites X-Forwarded-Proto and the app cannot be reached directly. The default IP callback reads REMOTE_ADDR, not spoofable forwarded headers. Behind a proxy, implement trusted ingress IP handling and test it; otherwise requests may share the proxy's lockout budget.

SMTP settings, .env, databases, uploads and browser QA credentials must never be committed. Production dependencies should be reviewed and refreshed routinely; requirements/lock.txt records the tested foundation environment.

Optional two-factor authentication can be added through the authentication backend/login layer, but **2FA is not implemented** in Phase 1. Registration abuse budgets and private upload validation are implemented. Public verification uses shared-database IP budgets; production-database concurrency verification remains pending.

## Reporting

Report suspected vulnerabilities privately to the organization’s designated security contact. That operational contact must be configured before public deployment; do not submit real applicant data in public issue reports.

## Public registration and uploads

Registration requires CSRF, validates every step on the server and revalidates active location/choice records on submission. Drafts are session-owned, expire after 24 hours and carry revisions to reject stale edits. Draft contents are cleared after submission. Anonymous users cannot retrieve another draft, portrait or receipt; private document downloads have no public route. Registration responses use no-store headers.

Abuse budgets use a keyed IP digest in the database: 10 starts/hour, 120 step POSTs/hour and 5 submission attempts/hour. Honeypots and a five-second minimum completion time add basic bot resistance. These are fixed windows, so adjacent windows may allow bursts. Shared networks may share a budget. No CAPTCHA or SMS/email verification service is integrated.

File streams have hard limits independently of per-file form validation. Random filenames, private filesystem permissions and no media URL mapping prevent direct public serving. Re-encoded portraits remove metadata and use a bounded 3:4 crop; document images are also re-encoded. PDFs are parsed and checked for encryption, page/object/depth limits and detected active content. PDFs are never rendered inline. This is not an antivirus guarantee. Production ingress must enforce body/time limits and operational malware screening should be considered before production staff downloads.

[Django's upload guidance](https://docs.djangoproject.com/en/5.2/topics/security/#user-uploaded-content) explains why validation alone cannot guarantee safe content. [Pillow's orientation helper](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose) is used before creating sanitized image derivatives.

Submission locks the system singleton and draft, allocates an application number, attaches existing private uploads and records consent and audit events in one transaction. File replacement cleans up old files after commit; new files are removed if database saving fails. A process crash between storage write and database commit can leave an unreferenced private file; storage reconciliation remains an operational concern. Draft pruning removes only expired temporary data, preserving submitted applications.

Duplicate checks are private warnings, not rejections or public existence checks. No contact details appear in receipt pages or audit submission metadata. Read-only emergency-admin inspection remains restricted to super administrators. Regional review/download workflows enforce application scope and action-specific capabilities.

## Review and correction

Review actions require CSRF, capability and jurisdiction checks, a valid state transition and a current revision. Restricted duplicate matches disclose no identifying information. Private downloads are audited and use attachment disposition; only sanitized portraits can be previewed.

Correction links carry a random secret in the URL fragment, store only its hash, expire after 48 hours and become unusable after resubmission, renewal or cancellation. A CSRF-protected exchange binds the grant to the applicant session. Same-origin referrer policy preserves Django CSRF checks without sending referrers cross-origin. Only requested fields can change. Application history records old/new values and file hashes; access remains scoped. Staff share links manually; no external notification is sent.

Approval locks policy and application records and creates identity, sequence, appointment, pending card metadata and audit history in one transaction. Production row-lock behavior must be validated on the selected PostgreSQL/MySQL deployment.

## Registry lifecycle

Registry scope follows the current/last appointment. Transfers require management scope on both source and destination and retain original identity tokens. Viewing scope cannot widen contacts or mutation privileges. Search does not match hidden mobile numbers. Panchayat institutional history can show the historical name/ID of a transferred person, while current contacts and detail links remain restricted. Appointment notes and decision reasons require management permission.

Lifecycle mutations and expiry maintenance serialize on the same policy lock as approval. Replacement closes the old appointment and approves the new application atomically, with all approval checks and revision checks retained. Revoked/replaced identities cannot reactivate. Scope checks, CSRF, no-store responses and append-only status history apply to registry endpoints. Portrait access is scoped; raw verification tokens never appear in registry responses.

## Public verification boundary

HTML and JSON receive the same allowlisted projection; staff sessions do not enrich public results. Optional contacts require policy plus applicant opt-in and active authorization. Public endpoints apply date/location/appointment checks, no-store/no-referrer/noindex headers and CSP. Failures return generic responses without debug locals. Tokens identify only the public projection and never unlock documents or staff actions.

QR generation uses PUBLIC_BASE_URL, never an incoming Host header. Token rotation requires scoped management, CSRF, revision, reason and acknowledgment; plaintext token values are excluded from audit/history. Request budgets use keyed IP digests, and Django logs redact verification paths. Proxy/server/CDN logs need equivalent operational configuration. See VERIFICATION.md for limits and response fields.

## Card artifacts

Generation, download/reprint and revocation use scoped capabilities, revision checks, CSRF and reasons. Card operators cannot revoke without management permission. Artifacts are stored privately under random paths; only current cards can be downloaded or previewed. Printable data is explicitly assembled without private personal/contact fields. PDF checksums are checked before downloads. Card-bound verification checks a separate random card token and never publishes source snapshots or revocation reasons. External logs must redact the card query parameter. See IDCARDS.md.

## Reports and exports

Dashboard totals and report rows are jurisdiction-scoped. Export capability is evaluated independently from viewing; mixed viewer assignments cannot widen exports. Contact permission is evaluated by location and skills/equipment require application access. Audit writes precede download responses; CSRF, required reasons and no-store headers apply. CSV/Excel neutralize formula-like text. Explicit report columns exclude private uploads, tokens, DOB, addresses, emergency contacts and administrative notes. In-memory exports have row caps; see REPORTS.md for semantics and operational limits.

## Phase 9 hardening

The custom application CSP permits same-origin scripts and blocks inline scripts, eval, objects, foreign form actions and framing. Inline styles remain allowed for existing visual controls. Public verification retains its stricter policy. Django emergency admin and Swagger are excluded from custom script CSP, but retain other security headers. Form pages use same-origin referrer policy (required for reliable local browser CSRF Origin behavior); verification pages use no-referrer. Browser media/geolocation permissions are disabled; selecting/uploading files remains supported.

Upload stream bounds now apply to correction and all other multipart routes. A stream rejection becomes HTTP 413 before any view executes, avoiding partial-file acceptance. Imports have a 5 MB stream cap. Other limits are 20 MB/file, 100 MB total, nine files; business validation can impose tighter limits. Ingress must also enforce body size and timeouts because application parsing may drain the remaining request body.

Report exports and card generation each allow 30 POST attempts/hour/account. Their salted database counters are independent of IP; fixed-window boundary bursts remain possible. Periodically run prune_security_records per retention policy to remove expired budgets. Reset uid/token paths and common credential query parameters are redacted from configured console logging; configure equivalent ingress logging restrictions.

Deployment checks reject overlapping private/public storage, non-HttpOnly sessions, wildcard CORS and non-HTTPS trusted CSRF origins. Production origins must be absolute HTTPS origins without credentials or extra path/query/fragment. Production session ages must be 60–86400 seconds. Existing default remains 1800 seconds. See PHASE9_REPORT.md for tested evidence and operational boundaries. Re-run scripts/audit_dependencies.py with approved network access after dependency changes; metadata availability is not a security guarantee.

## Deployment proxy normalization

TRUSTED_PROXY_CIDRS defaults empty. Only explicitly trusted direct peers can supply a single validated X-Real-IP. Middleware normalizes REMOTE_ADDR once, removes forwarded chains and DRF uses NUM_PROXIES=0. Nginx must overwrite these headers and Gunicorn must remain bound behind the proxy. The supplied deployment CIDR/gateway is an example that must match the actual host network. Internal readiness is blocked at Nginx; local readiness reports generic database availability only.

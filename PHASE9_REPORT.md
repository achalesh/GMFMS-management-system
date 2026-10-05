# Phase 9 — Security Hardening

Completed 2026-10-04. This is a source review and application regression audit, not an external penetration test or a production infrastructure certification.

## Findings fixed

| Finding | Resolution | Evidence |
| --- | --- | --- |
| Correction uploads bypassed registration stream limits; imports buffered before size validation | Global upload stream bounds; imports capped at 5 MB, other uploads 20 MB per file / 100 MB combined / 9 files. Middleware rejects truncated multipart requests with 413 before views can accept partial data. | Correction, unknown-route, import, combined-size and file-count tests; six-step browser upload run |
| Password-reset and query credentials were not covered by verification-token log redaction | Log filter redacts reset uid/token paths and token/card/access_token/reset_token query values, preserving structured argument formatting | Redaction regression tests |
| Custom pages lacked a baseline script/object policy | Same-origin scripts/connections, no objects, restricted forms/base/frame embedding; Permissions-Policy and opener isolation. Public verification/private-file policies stay stricter. | Header tests, real-browser inline-script rejection, registration/report browser workflows |
| Report exports and card generation lacked expensive-operation budgets | Separate 30 POST attempts/hour/account budgets using shared database counters; changing IP does not bypass them; 429 with Retry-After | Account isolation, IP-change and pre-render rejection tests |
| HTTPS-only public URL validation accepted malformed origins | Reject missing hostname, embedded credentials, paths, queries, fragments and invalid ports; constrain production session duration to 60–86400 seconds | Production configuration negative tests |
| Public/private storage separation and cookie/CORS invariants lacked deploy checks | Register gmfms.E001–E004 for overlapping storage, non-HttpOnly sessions, wildcard CORS and HTTP CSRF trusted origins | Positive/negative check tests and actual production check command |

Browser testing caught Origin:null on local form submissions with a global no-referrer policy. The delivered policy is same-origin for form pages, retaining no-referrer on public verification pages; CSRF checks remain enabled and unmodified. Inline styles remain allowed for current crop/error-page styling; inline scripts and eval are not allowed. Emergency Django admin and Swagger are excluded from the custom CSP because of their own script requirements; frame denial, nosniff, referrer and other baseline headers still apply.

## Permission and privacy audit

Reviewed capability/scope checks, private record/file access, public projection, exports, emergency admin entry, upload validation, session/cookie configuration and logging. Regression coverage verifies anonymous denial, district and mixed-role scope, CSRF on sensitive writes, session rotation/logout/expiry/disabled-user denial, contact restrictions and public-field allowlists even for logged-in administrators. Public portrait URLs deliberately contain the already-present verification token; private database UUIDs and administrative fields remain absent. No generic private-media filesystem route is served.

Existing protections remain: password hashing/validators, login lockout, password-reset limits, public verification budgets, approval/lifecycle transaction boundaries, append-only audit model protections, upload image re-encoding and PDF active-content rejection. No change grants new role permissions. Sensitive operations still require their existing reasons, revision checks and audited service calls.

## Dependency review

scripts/audit_dependencies.py queried the public PyPI per-version JSON vulnerability metadata for all 36 entries in requirements/lock.txt. All requests succeeded and no non-withdrawn advisory was returned for these versions. Results are saved under ignored artifacts/dependency-audit.json. This is a metadata check, not proof that dependencies have no vulnerabilities, and excludes OS/native-system components.

Django's minimum supported patch in the requirements is now 5.2.17, matching the installed/tested version and the [official August 2026 security release](https://www.djangoproject.com/weblog/2026/aug/04/security-releases/). No package upgrade or lockfile change was needed. Dependency consistency passes.

## Verification

- 300 automated tests passed (283 prior tests plus 17 hardening tests, with expanded production-configuration cases).
- Full anonymous registration: live location dropdowns, six steps, photo crop, PDF upload, consent and private receipt; desktop/tablet/mobile checks passed.
- Sign-in, dashboard drilldowns, nine report views and CSV/Excel/PDF downloads passed under the new policy.
- Browser security check confirmed injected inline JavaScript is blocked and normal external application scripts work.
- Production-settings `check --deploy` passed with an ephemeral secret, HTTPS origin, explicit hostname and PostgreSQL backend configuration. The earlier Windows PostgreSQL-driver import problem did not recur. This check does not connect to a production database or validate transaction concurrency.
- Django checks, migration drift, schema validation, lint/format, pip check and static collection passed. No new migrations or pending migrations.

## Files and operational limits

Added apps/common/middleware.py, apps/accounts/checks.py, tests/test_hardening.py, scripts/audit_dependencies.py, scripts/ui_security_check.cjs and this report. Updated upload handler, shared budget service, report/card views, log filter, settings, account app startup, configuration tests, Django minimum version and operational documentation. No new models or routes.

All browser mutations used the isolated synthetic QA database. Real applications, facilitators and cards were not changed. No Git repository is present, so no commit was created.

Before internet deployment (Phase 10): verify HTTPS/proxy header handling and real client IP at ingress, enforce request-body/time limits there, test target-database locking, configure retention/pruning and audit DB privileges, establish backups/restore tests, and configure the incident contact. Fixed-window budgets permit boundary bursts and need operational sizing. Upload validation is not antivirus scanning; parser isolation/antimalware remain infrastructure considerations. Development DEBUG is intentionally retained only for local development. Run production with config.settings.production. No external infrastructure changes or public deployment were performed.

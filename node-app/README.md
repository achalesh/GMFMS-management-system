# Node.js migration — foundation preview

This preview includes the foundation, registration/review, corrections, facilitator lifecycle, QR verification, ID cards, dashboards and reports migration stages for Hostinger Web App hosting. It is not a production replacement yet. The original Django application and its records remain the working system.

Implemented: Express sign-in, database-backed 30-minute sessions, CSRF protection, login throttling, live account/role checks, jurisdiction-filtered Kerala directory (14 districts, 152 blocks, 941 panchayats), original logo and Malayalam tagline. No real accounts or private records have been imported.

Registration at `/register/` now includes a six-step, session-owned 24-hour draft; Kerala hierarchy validation; personal/professional/equipment details; bounded private uploads; normalized/cropped portraits; PDF active-content rejection; review and explicit consent; and an idempotent submission reference. `/applications/` supports jurisdiction-scoped review, rejection with a reason, and approval into an initial facilitator record. Revisions prevent stale updates; approval revalidates details/consent, requires duplicate acknowledgement with a reason, and serializes primary appointments.

Uploads are currently stored privately in the database as bounded base64 content, not in deployment files or public assets. The MySQL deployment must verify packet limits above the largest encoded upload (about 7 MB), storage quota and backup/restore performance. Supporting documents are optional in this stage. Configurable document requirements remain to be ported. Exact mobile/email/name-and-panchayat duplicates are checked; Django fuzzy-name warning parity remains pending. Existing Django runtime settings have not been imported.

## Local use

From `node-app`, use Node 24 and install dependencies with `pnpm install --frozen-lockfile`. Run `node scripts/migrate.js`, then `node src/server.js`. The preview is on http://127.0.0.1:3000. Local development uses a separate SQLite database in `var/`.

Create a separate account using `node scripts/create-admin.js` with ADMIN_USERNAME, ADMIN_EMAIL and ADMIN_PASSWORD supplied securely through the process environment. Passwords require at least 12 characters. Existing Django credentials are not automatically available. Never commit credentials. Set a stable random SESSION_SECRET in a private .env to retain sessions across server restarts.

Validation: `node scripts/check-build.js` and `node --test`. Tests cover location seed idempotency/counts, passwords, production configuration rejection, jurisdiction boundaries, login session rotation, CSRF, logout, disabled accounts, and throttling.

## Remaining before deployment

- Port configurable registration requirements and administration. Appointment changes are retained as before/after history snapshots in this version; verify migration of the Django appointment tables before production.
- Build and verify a repeatable private-data migration with reconciliation and rollback.
- Test all database operations against Hostinger MySQL. Only the SQLite path has been exercised locally.
- Verify database-backed uploads against Hostinger MySQL, including persistence through redeploy and restoration from backup.
- Verify Hostinger proxy topology, secure cookies, TLS, backups, restore, scheduled cleanup of expired sessions/budgets, and production feature parity.

Use a dedicated MySQL database. Production configuration requires MYSQL_URL, HTTPS APP_ORIGIN, and SESSION_SECRET of at least 50 characters. Set TRUST_PROXY_HOPS only after validating the actual proxy path. The start command is `node src/server.js`; build validation is `node scripts/check-build.js`. Run schema/seed migration separately before start. Do not point gramaswaraj.in at this incomplete preview.

Official hosting references:
- https://www.hostinger.com/support/how-to-deploy-a-nodejs-website-in-hostinger/
- https://www.hostinger.com/support/connecting-a-hostinger-mysql-database-to-a-node-js-application/

## Registration verification and maintenance

`node --test` exercises field validation, document processing, draft revision/step checks, required consent, idempotent submission, duplicate approval acknowledgement, simultaneous primary appointment attempts, private file boundaries and reviewer permissions. `node scripts/ui-registration-check.js` is an optional Playwright/Chrome browser check; provide Playwright on NODE_PATH. It creates only in-memory synthetic records and ignored screenshots in var/.

Run `node scripts/maintenance.js` periodically to remove expired unsubmitted drafts and their uploads, expired sessions and throttle records. Submitted application documents are retained for review. No real private data was copied from Django.

## Corrections and facilitator lifecycle

Staff can request selected field/document corrections, renew or cancel the request, and share a one-use 48-hour link manually. Only a token digest is stored. The browser receives the token as a fragment, removes it from the displayed URL, and exchanges it through a CSRF-protected POST. A correction session exposes only requested fields. Resubmission revalidates the full application, renews required consent, preserves optional publication choices, records changed field names and returns the application to SUBMITTED. Old links cannot be reused after resubmission, renewal or cancellation.

The registry supports reference/notes, suspension, inactivity, resignation, revocation, reactivation, renewal, transfers, role changes and transactional replacement from a reviewed application in the same panchayat. All changes require a reason and revision, recheck live staff permissions and record before/after snapshots. Transfers check source and target jurisdiction. Revoked/replaced identities cannot be restored. A failed replacement approval rolls back the predecessor change. Expiry is effective immediately when reading records and materialized by maintenance, which also releases expired primary occupancy. MySQL integration remains unverified.

Fifteen automated test groups and the browser walkthrough cover registration, applicant corrections, review/approval and suspension/reactivation. Browser QA uses separate in-memory synthetic records only.

## QR verification and identity cards

Staff open a facilitator’s Verification and ID cards page to create a link or issue a card. Identity tokens and card tokens are independent random 256-bit values. Public HTML and JSON verification use an explicit allowlist and no session cookie, no-store/no-referrer/noindex headers, generic failures and per-IP throttling. Contact details, private documents, application payloads and internal notes are never published. Contact publication defaults to disabled. Administrators may enable individual contact types; publication also requires applicant consent and a currently authorized identity/card.

A card is current only when its identity and location are active, its validity has not elapsed, and the current appointment/portrait/branding/origin matches its stored source fingerprint. Reissues supersede older versions; revocation disables card authorization immediately. Token rotation invalidates earlier verification URLs. Downloads require live cards.issue permission, a reason and current revision, check content hashes, and record an audit event. Revocation additionally requires facilitators.change.

Cards contain a front/back CR80 PDF and a one-page A4 cut-out sheet (print at actual size). Latin and Malayalam fonts are embedded and unsupported characters or overflowing text fail issuance instead of silently disappearing. Development PDFs carry a preview watermark. Production settings, organization-specific signatory details, deployment URL and printer calibration must be verified before real issuance. No signatures are invented. The PDF assets live privately in the database. Existing issued Django cards have not been imported or changed.

QA: synthetic PDFs were rendered and visually checked; QR codes decoded from both the rendered card and A4 sheet. Browser QA covers PDF download and public revocation status. Test artifacts in var/ are development samples, not issued credentials. Configure production reverse-proxy logs to redact verification paths and card query tokens before deployment. MySQL integration and Hostinger deployment remain pending.

## Dashboards and reports

The dashboard shows real active location totals, active facilitators, primary coverage, vacancies, pending applications (where permitted), suspensions, expiries and identities expiring within 30 days. District summaries use the same current authorization rules. Report screens support coverage, registration progress, skills, equipment, appointment change history, vacancies, facilitators, applications and expiring identities; pages contain up to 50 rows. Filters reject invalid dates, incompatible statuses and locations outside the permitted hierarchy.

Excel, CSV and PDF downloads require live reports.export authorization, CSRF, an export reason and a per-user export budget. Export jurisdiction is checked separately from dashboard visibility. Mobile values require contacts.view for each row; application counts and skill/equipment data require application access. Export metadata (report, filters, row count, format, actor and reason) is recorded without copying contact values into the audit log. CSV values are protected against spreadsheet formula execution and Excel cells use explicit text/numeric values. The Excel report freezes headings, filters columns, wraps text and adjusts row heights. PDFs use embedded Latin/Malayalam fonts, repeat headings, wrap cells and show page numbers; PDF exports are capped at 500 rows, with Excel/CSV available for larger selections. Reports are bounded to 10,000 underlying records.

The history report describes before/after appointment changes recorded by the Node registry. It is not a migration of the original Django appointment ledger. An event is shown only when both its old and new panchayats belong to the selected permitted locations, so a restricted report cannot disclose a transfer destination outside its scope. Configurable report publication is not enabled. Existing Django records have not been imported.

Validation: fifteen automated groups passed; the browser walkthrough checked the mobile dashboard, report filters and all three export formats. Synthetic report PDFs were rendered and inspected, and Excel files were reopened to verify string/numeric types and filters. Hostinger/MySQL deployment, real-data reconciliation and remaining administration features are still pending.


## Administration and deployment preparation

Administration provides staff accounts, jurisdiction-based roles, session-ending deactivation/password resets, mandatory initial password changes, organization branding, registration/document/privacy policy and a paginated audit viewer. Changes require reasons and revision checks. Removing the last account manager is blocked. The exact Malayalam tagline remains in the header.

Read HOSTINGER.md for the staged deployment procedure. Run `python scripts/package-hostinger.py` locally to build the allowlisted ZIP. Default startup requires the current schema; RUN_MIGRATIONS and BOOTSTRAP_ADMIN are explicit first-release switches. Remove bootstrap secrets after successful initialization. No existing Django data is bundled or migrated.

## Migration readiness

MIGRATION.md describes the private Django snapshot export and verified integrity assessment. The source and Node operational database remain unchanged. `node scripts/check-mysql.js` checks a configured staging MySQL connection, Unicode support, upload capacity and transactional rollback; Hostinger validation awaits database creation.

## Applicant cancellation

Unfinished drafts can be discarded from the wizard after confirmation; the draft and its uploads are deleted. Submitted applications awaiting a decision can be withdrawn from the confirmation page in the same browser session, with a reason, revision check and confirmation. Withdrawal retains the application/documents and audit/review history, invalidates correction tickets and removes it from pending counts. Approved/rejected applications cannot use this action. No public lookup by reference number grants cancellation access; support-assisted recovery for a lost applicant session remains future work.

## Membership limits and contact uniqueness

A panchayat may have at most three current appointments. Active, suspended and inactive appointments with unexpired validity and no recorded end count toward this limit. Approval, transfer, renewal and reactivation enforce capacity under the shared transaction lock; permanent revocation, replacement, resignation and expiry release occupancy. Pending applications may still be submitted. One primary per panchayat remains enforced.

Mobile numbers and nonblank email addresses cannot repeat across submitted applications, including historical, rejected or withdrawn records. Email matching ignores case. Registration saves, submission, correction and approval enforce this rule, and duplicate acknowledgement cannot override it. Blank email addresses are allowed. Existing records are not removed or changed by these checks.

To end membership permanently, open Facilitators, select the member, choose Revoke permanently, enter a reason and save. Revocation prevents reactivation and invalidates public authorization; records and audit history are retained. This is not personal-data erasure.

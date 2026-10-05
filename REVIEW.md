# Application review and approval

Staff inbox: /applications/. The Applications sidebar entry is available to authorized reviewers. Applicant registration remains /register/media-facilitator/.

## Access

| Role | Application access |
| --- | --- |
| SUPER_ADMIN / STATE_ADMIN | Statewide review, corrections, approval and rejection |
| DISTRICT_ADMIN | Review, corrections, approval and rejection in assigned districts |
| BLOCK_COORDINATOR | Review and corrections in assigned blocks; no approval or rejection |
| REVIEWER | Review and corrections within assigned scope; no approval or rejection |
| VIEWER / ID_CARD_OPERATOR | No private application inbox or document access |

These follow the existing capability policy. A separate broader viewing role never broadens a narrower approval role. Inactive or unresolved regional jurisdictions grant no regional access. Record lists, counts, filters, detail pages, actions and private files enforce scope on the server.

## Staff workflow

1. Open Applications. Pending review is the default filter. Search by name, Malayalam name, mobile or application number; combine status, District, Block, Panchayat and submission dates.
2. Open an application to inspect its details, consent, private photo/documents and duplicate matches.
3. Choose Start review. This records the reviewer and changes SUBMITTED to UNDER_REVIEW.
4. Request corrections, approve or reject. Every mutation checks the displayed revision; stale tabs must reload.

Documents download as authenticated attachments with no-store, nosniff and sandbox headers. Sanitized portraits alone may be displayed inline to authorized reviewers. File access and application viewing are audited.

## Corrections

From UNDER_REVIEW, choose Request correction. Enter instructions for the applicant and select specific editable fields. Those instructions are public to the correction-link holder; other internal review notes are not.

Panchayat, district, application number, status, staff decisions and identifiers are never applicant-editable. If the original Panchayat is wrong, reject with an explanation and request a new application; a boundary-changing administrative workflow has not been introduced.

After confirmation, copy the private link displayed on screen and share it directly through an approved contact channel. **The application does not automatically send email, SMS or WhatsApp messages.** The complete link appears only in that response.

Links expire after 48 hours. The secret is in the URL fragment (#...), which browsers do not send in HTTP request paths. The access page removes the fragment from browser history, fills an access-code field and exchanges it through a CSRF-protected POST for a session grant. Only a SHA-256 digest is retained in the correction-request table. The session grant is checked against status, expiry, revocation and use on every request.

The applicant edits selected fields, replaces selected files when needed and reconfirms consent. Other posted fields are ignored and cannot change the application. At least one requested change is required. On successful resubmission the application returns to SUBMITTED, the link is consumed and the session grant is removed.

Renew correction replaces previous links while retaining the selected fields and applicant instructions. Cancel correction revokes outstanding links and returns the record to UNDER_REVIEW without changing applicant details. Both require a reason.

Changes are preserved in append-only, application-scoped history: prior/new field values, document checksums, actor and timestamp, with consent version/text/timestamp snapshots. Old replaced file contents are deleted after successful commit; their checksums remain in history.

## Approval

Approval is available only from UNDER_REVIEW to authorized approvers. Confirm that details, documents and recorded consent were verified. Duplicate warnings require acknowledgement plus an explanatory reason; fuzzy matches alone do not reject an application.

Duplicate warnings are recalculated on the detail screen and before approval. Matches outside the viewer's scope are redacted. The inbox's saved-match count is a snapshot refreshed during review/correction; the detail screen provides current checks.

An existing active primary appointment blocks another PRIMARY approval when the one-primary policy is enabled. Approval also offers ASSISTANT and ADDITIONAL appointment roles, which do not fill primary vacancies. Turning that policy off permits multiple primary appointments through the same audited service. Inactive/expired facilitator and appointment dates are considered. Replacement and lifecycle management are available in the facilitator registry; see REGISTRY.md.

One transaction:
- locks policy and application records, validates state/revision/permission/details/files/consent;
- checks current duplicates and appointment conflict;
- allocates a per-district sequence and unique GS-MF-DISTRICT-0001-style number using the configured prefix;
- creates a Facilitator, the selected FacilitatorAppointment role, random verification token and pending IdentityCardMetadata;
- records the decision and append-only review/audit history.

A critical failure rolls back the entire operation, including number allocation. Repeated or stale approvals cannot create a second identity. Validity uses the configured default validity days.

These minimal identity/appointment records are necessary to implement approval consistently with the specification. Registry browsing, replacement and history workflows are now available. Public QR verification is available through the registry; card rendering/issuance remains a later phase. The token is not shown in review pages or audit logs.

## Rejection

Only authorized approvers can reject from UNDER_REVIEW. A reason is mandatory. The application and its history remain; rejection creates no facilitator or appointment. Approved/rejected records have no reopen or delete action in this phase.

## Operations and validation

Set PUBLIC_BASE_URL to the actual HTTPS origin before sharing correction links. Local links only work on this computer. Do not log request bodies or copy private links into public logs/tickets.

Tests cover scope enforcement, state transitions, stale revisions, duplicate acknowledgement, active-primary conflicts, token expiry/replacement/reuse, correction allowlists, CSRF, file privacy and rollback. SQLite cannot prove production row-lock behavior. Run concurrent approval tests on the selected PostgreSQL/MySQL server before live rollout.

Browser fixtures are isolated: run scripts/prepare_ui_check.py then scripts/prepare_review_ui.py; start the QA server with DATABASE_URL pointing to artifacts/ui.sqlite3, MEDIA_ROOT=artifacts/ui-media and PUBLIC_BASE_URL=http://127.0.0.1:8001; run scripts/ui_review_check.cjs. Prepare fresh review fixtures before repeating the browser workflow because approvals/rejections are terminal.

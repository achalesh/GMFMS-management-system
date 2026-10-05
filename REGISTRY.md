# Facilitator registry operations

Open /facilitators/ after signing in. Approval automatically creates an identity, current appointment and initial history event. Public token verification is available in Phase 6; there is no public browsing directory.

## Access and privacy

All existing staff roles can browse identities within their facilitator-view jurisdiction. Super/state administrators and assigned district administrators can manage them. Block coordinators and reviewers have scoped read access and private contacts; VIEWER and ID_CARD_OPERATOR cannot retrieve or search private contacts. Broader viewing assignments never widen management or contact scopes.

Registry pages show approved identity information, current/last appointment, validity and appointment history. Portraits use an authenticated, scoped endpoint. Private application documents require the separate application-review permission and original application scope. Verification tokens, addresses, dates of birth and emergency contacts are never sent in registry pages. Internal reasons, references and notes appear only to registry managers. No external messages are sent.

## Search and coverage

Search official ID, English/Malayalam name, application number, Panchayat, block or district. Mobile search only matches records for which the user has contact permission. Combine location, effective status, appointment role, registration date, approval date and expiry filters.

Coverage at /facilitators/coverage/ supports district and block drill-down, Panchayat search and a vacant-only filter. Only active institutional locations are counted. Coverage counts distinct Panchayats with an ACTIVE PRIMARY appointment, an ACTIVE facilitator, current validity, no ended timestamp and applicable effective dates. Assistant/additional roles do not fill primary vacancies. Multiple primary appointments under the configurable policy count as one covered Panchayat.

Panchayat profiles preserve current appointments, previous appointments, dates and scoped application links. A transferred person's old Panchayat retains their historical name and ID, but does not expose current contacts or link to their record unless the viewer also has access to the current jurisdiction.

## Management actions

Every action is POST-only, CSRF-protected, revision-checked and requires a reason. Operations take effect immediately; backdating and scheduled transfers are not supported.

- Edit appointment details: update the current appointment reference and private notes; retain old/new values in history.
- Suspend / mark inactive: stop authorization while retaining the current appointment.
- Record resignation: end the appointment and mark the identity inactive.
- Reactivate: restore a valid inactive/suspended identity; after resignation, create a new appointment instead of reopening the closed one. Reject conflicting primary appointments.
- Renew validity: extend beyond both today and the existing expiry, at most ten years ahead. An expired active/EXPIRED current appointment becomes active after conflict checks. Suspended/inactive identities retain their status. A resigned appointment remains closed until reactivation.
- Transfer: close the old active appointment and create one in the destination Panchayat. The actor must have management permission in both locations. Retain the original facilitator ID and token, including its original district abbreviation.
- Change role: close the current active appointment and create a PRIMARY, ASSISTANT or ADDITIONAL appointment. Primary promotion checks vacancies.
- Revoke: permanently end authorization. Revoked identities cannot be reactivated. Existing closed appointment dates/reasons are preserved.
- Replace facilitator: select an UNDER_REVIEW application for the same Panchayat, verify its details/documents/consent and acknowledge duplicate warnings with the decision reason. End the outgoing primary appointment and mark that identity REPLACED; approve the incoming application and create a new ID/appointment in the same transaction. Failure rolls back both sides, numbering and history. Stale incoming applications are rejected. Replaced identities remain historical and cannot reactivate.

Approval offers PRIMARY (default), ASSISTANT and ADDITIONAL roles. Assistants and additional facilitators may be approved alongside a primary without changing the one-primary policy. Replacement always creates a new primary appointment.

## Expiry and history

Expiry is effective immediately after valid_until, even if maintenance has not run. Run daily:

~~~powershell
.\.venv\Scripts\python.exe manage.py expire_facilitators
~~~

This idempotent command records expired active identities and their status history. It does not modify suspended, inactive, replaced or revoked identities. The existing valid-until date is inclusive.

FacilitatorStatusHistory records actor, time, action, previous/new status, reason, appointment and old/new snapshots. The table and global audit are application-level append-only. Database owners retain direct access; production privileges and external retention are deployment responsibilities.

Migrations attach existing approved identities to their latest existing appointment and add an explicitly labelled registry-import history event. Existing approval timestamps, IDs and tokens are preserved. Original submitted application locations remain unchanged after transfer.

## Operational limits

All operations share the policy-row transaction lock used by approval. PostgreSQL/MySQL row-lock/concurrent-worker behavior still needs integration testing on the actual production engine; local SQLite tests do not establish those guarantees. Data edits outside supported services bypass invariants.

Public QR verification is implemented; see VERIFICATION.md. Card rendering/versioning is available in Phase 7; see IDCARDS.md. Renewal makes existing cards outdated and requires a newly generated version. Reports/exports remain Phase 8.

For isolated browser QA, prepare_ui_check.py migrates/seeds artifacts/ui.sqlite3, then prepare_registry_ui.py adds synthetic fixtures. Start port 8001 with that database, MEDIA_ROOT=artifacts/ui-media and PUBLIC_BASE_URL=http://127.0.0.1:8001; run scripts/ui_registry_check.cjs. Prepare new registry fixtures before rerunning the terminal replacement flow.

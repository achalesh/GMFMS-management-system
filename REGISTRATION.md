# Public Media Facilitator registration

Open /register/media-facilitator/ or choose **Apply as a Media Facilitator** on the staff login page. Applicants do not need staff accounts.

## Application journey

1. Choose District → Block → Grama Panchayat from the active location master.
2. Enter personal/contact details. Mobile numbers accept ten digits or +91; blank WhatsApp uses the mobile number. Name, mobile, address and PIN are required. Malayalam name, email, gender, date of birth and emergency contact are optional. If an emergency contact is provided, all three contact fields are required.
3. Select skills and languages; enter professional experience. At least one language is required. Selecting Other requires an explanation.
4. Select equipment and optionally supply HTTP(S) social profile links.
5. Upload a portrait and configured documents. Crop controls adjust the portrait in a 3:4 frame without distortion. Continuing saves the cropped, compressed JPEG. Optional documents can be removed; choosing another file replaces the slot.
6. Review all sections, accept the two required consents and submit. Mobile/email/social publication opt-ins are separate and unchecked by default.

A successful submission generates GMF-APP-YEAR-000001-style numbers. Save the number. No facilitator ID, appointment, approval or QR is issued here.

## Drafts and receipts

The server stores draft information; the browser session contains only the draft reference and start time. A draft expires 24 hours after creation. The existing browser session policy also applies (30-minute lifetime by default and expiry on browser close). There is no email-based or cross-device draft recovery.

The start page offers Continue or Delete draft. After submission, temporary draft data is cleared and files are attached to the application. The receipt is available only in the originating browser session while its draft reference remains valid. It shows the application number/time/status, not private contact information. Phase 3 does not send confirmation emails or offer public status lookup.

Run daily to delete expired draft rows and their draft files:

~~~powershell
.\.venv\Scripts\python.exe manage.py prune_registration_drafts
~~~

Submitted applications and their files are retained. This command does not implement a policy for deleting submitted records.

## Choices and document requirements

Skills, equipment, languages and four document types are seeded by migrations. All documents are optional initially; the portrait is required. This avoids inventing an organizational requirement for identity proof.

~~~powershell
.\.venv\Scripts\python.exe manage.py seed_registration_choices
.\.venv\Scripts\python.exe manage.py configure_registration_document recommendation --actor admin --required yes --reason "Approved registration policy"
.\.venv\Scripts\python.exe manage.py configure_registration_document identity --actor admin --active no --reason "Identity proof is not required for intake"
~~~

Document codes: recommendation, identity, certificate, other. The command supports --required yes/no, --active yes/no and --instructions TEXT and writes an audit event. Re-running seeds creates missing choices without overriding configuration. Upload size and consent version are configured through existing System & privacy settings.

## Private uploads

Default limit: 5 MB per file, configurable up to 20 MB. Stream-level hard bounds: 20 MB per file, 100 MB per request, nine file parts. Configure the reverse proxy's body limit to at most 100 MB and a suitable request timeout; Django's non-file request memory limit alone does not bound uploaded file streams.

Images must decode as their declared JPG/PNG format, contain at most 20 megapixels and, for portraits, be at least 100 pixels per side. They are re-encoded with orientation applied and metadata removed. Portraits are at most 600×800; document images at most 2400×2400.

PDFs must parse, be unencrypted, have 1–30 pages, and contain no detected scripts, active actions, embedded files or interactive forms. Parsing is bounded by input size and object/depth limits. These checks are not an antivirus service. PDFs remain private and are not embedded or served by a public route.

Storage filenames are random UUIDs under private_media/registrations/. Never configure a public alias for private_media. Applicant portrait previews require the originating session; there is no public document-download route. Authorized reviewers can inspect and download private files from the scoped application review screen.

## Duplicate warnings and administration

Submission checks existing applications for matching mobile, email, Panchayat and similar names. Name comparison uses normalized names and a four-character prefix to select candidates, plus a similarity threshold; it is a warning heuristic and may miss spelling changes outside that candidate set. No submission is automatically rejected for a match. Approval also checks active primary appointments against the configured one-primary-per-Panchayat policy.

Warnings are private. Super administrators with emergency-admin access can inspect read-only applications and warnings at /admin/registrations/application/. Emergency-admin records remain read-only. Regional review, correction, approval and rejection are available through /applications/; see REVIEW.md.

## Validation and rollout

Automated tests use temporary media directories. Browser tests use artifacts/ui.sqlite3 and artifacts/ui-media, never the main application database. Run the fixture preparer, start the QA server with MEDIA_ROOT=artifacts/ui-media, then run scripts/ui_registration_check.cjs with Playwright available.

The development URL is local to this computer. It is not a publicly hosted registration service. Before public deployment, verify HTTPS/proxy/upload limits, source-IP handling, production database concurrency, backups, retention and the organization's final privacy/document policy.

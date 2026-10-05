# Dashboards and reports

Sign in and choose **Overview** or **Reports** in the sidebar. Overview drills down from district to block to permanent panchayat profiles. Block dashboards include facilitator names, IDs, registration dates and permitted mobile numbers.

## Reports and filters

The report selector provides coverage, vacancies, facilitators, applications, expiring identities, skills, equipment, monthly registration progress and appointment history. Combine district, block and panchayat filters. For personnel reports use current status, role, and inclusive registration/approval/expiry dates. Application reports use registration dates and workflow status; **Pending** combines submitted, under review and correction required. Choose Rejected for rejection reports. Choose Active or Suspended in facilitator reports for those lists.

Coverage and vacancy reports are current snapshots and accept location filters only. Monthly registration progress groups submission month by the application's current status; it does not reconstruct historical decisions. Appointment history preserves recorded appointment status and scopes each row to the historical appointment's panchayat. Its approval filter uses appointment approval date; expiry uses effective-to (open-ended rows do not match a bounded expiry filter). Other facilitator reports use current appointment location, current authorization and the earlier of identity validity/appointment end. Skills/equipment require application access as well as facilitator access; original applications outside that access are omitted.

## Calculation definitions

Only active panchayats under active blocks, districts and states form the location denominator. Approved facilitators count retained identities at those locations, including former/replaced identities. Active means the same current authorization rule as public verification: valid identity and current appointment, effective today, not ended, with active location hierarchy. Covered counts DISTINCT panchayats with at least one active PRIMARY; assistants and additional facilitators do not fill vacancies. Vacant = total active panchayats minus covered. Expiring includes active authorizations with their earliest end date from today through today + 30 days, inclusive. Multiple primary appointments never inflate covered panchayats. Pending counts require application permission and may cover a narrower jurisdiction than facilitator totals for mixed-role accounts.

## Downloads

Choose Excel, CSV or PDF, enter a purpose/reason, then Download report. This is a CSRF-protected POST. Export scope is evaluated independently using reports.export; a broader viewer role cannot enlarge it. State/super administrators and district administrators have export capability by default. Every download writes reports.exported before sending file bytes. Audit records contain report, filters, row count, format and reason, not exported contacts. Failures to audit prevent download.

Mobile is included only where contacts.view permits it; otherwise it reads Restricted. No DOB, address, documents, emergency contacts, notes, verification tokens, or private upload paths are exported. Viewing alone generates no export event. Reports/downloads are no-store.

Excel has styled headings, wrapped cells, frozen headers, autofilters and print settings. CSV uses UTF-8 BOM for Malayalam/Excel compatibility. Formula-like text beginning with =, +, -, or @ (including leading whitespace) is apostrophe-prefixed; disallowed control characters are removed. PDF uses A4 landscape, embedded Latin/Malayalam fonts, shaped Malayalam, repeated headers and page numbers. Unsupported PDF glyphs produce a validation message recommending Excel/CSV.

Preview pages contain 50 rows. Downloads contain all matching rows in export scope, not just the preview page. Source queries are bounded at 10,000 records; narrow location filters for larger datasets. PDF is limited to 1,500 result rows. Exports are generated in memory and are not persisted to public storage. This is a live operational snapshot, not a transactionally frozen historical warehouse. Large-scale/background reporting and production concurrency benchmarking are outside Phase 8.

## Routes and local commands

- `/` — state/permitted-jurisdiction overview
- `/dashboard/districts/<id>/` — district/block progress
- `/dashboard/blocks/<id>/` — block/panchayat progress and facilitators
- `/reports/` — preview and POST download with the same query-string filters

No new database models or migrations are needed. Run `.\.venv\Scripts\python.exe manage.py migrate`, then `.\.venv\Scripts\python.exe manage.py runserver`. Run reports tests with `.\.venv\Scripts\python.exe manage.py test tests.test_reports --settings=config.settings.test`.

Security budget: at most 30 export POST attempts per hour per account. A 429 response includes Retry-After.

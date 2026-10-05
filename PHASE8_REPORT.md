# Phase 8 — Dashboards and Reports

## Delivered

State, district and block dashboards now show real scoped application, authorization, vacancy and coverage figures. District/block links drill down to panchayat profiles. Nine report types support location, status, role and date filters, paginated previews and Excel/CSV/PDF downloads. Pending combines all unresolved workflow states. Skills/equipment require application permission. Appointment history retains historical location scope.

Exports enforce their own role jurisdiction, redact unauthorized contact data, exclude private fields, require a reason and CSRF-protected POST, record audit events, neutralize spreadsheet formulas and use no-store responses. PDF rendering embeds and shapes Malayalam, repeats table headers and adds page numbers. See REPORTS.md for exact metric definitions, permissions and limits.

## Created and modified

Created apps/reports/{__init__,data,forms,exporting,views,urls}.py; templates/reports/{index,limit}.html; static/css/reports.css; tests/test_reports.py; scripts/ui_reports_check.cjs; REPORTS.md and this report. Updated dashboard views/URLs/template, base navigation/footer, config URLs/installed apps, README and security documentation.

No database models or migrations added. No role grants changed. No real application, appointment, facilitator or card was mutated for validation. No new dependency installation was required. The workspace has no Git repository, so no commit was made.

## Validation

All 283 automated tests passed on 2026-10-04 (256 prior tests and 27 new report tests). They cover empty/zero-denominator calculations, distinct primary coverage, assistant/future/ended/expired appointments, suspension, validity boundaries, inactive locations, date/status/hierarchy validation, district/block/mixed-role scope, contact redaction, historical transfer access, formula injection, export reasons/CSRF/authentication/audit failures, pagination, unsupported PDF glyphs, row limits, repeated page headers, and query-count stability as records grow.

Browser validation on an isolated synthetic database passed state/district/block drilldowns, all nine report views, actual CSV/Excel/PDF downloads, 1440/768/390/360 layouts and no JavaScript errors. Downloaded Excel and PDF contents were reopened and checked. Standard and three-page Malayalam PDFs were rendered and inspected; no clipping or overlapping table content was found. Synthetic QA exports remain under ignored artifacts and are not official issued reports.

Django checks, migration drift, schema validation, lint/format and static collection passed. No migrations were pending. The main server was restarted; its health endpoint, authenticated dashboard and reports returned HTTP 200. Existing production PostgreSQL DLL restriction remains documented in Phase 7; local SQLite checks do not establish production concurrency performance. Next phase is Phase 9 security hardening.

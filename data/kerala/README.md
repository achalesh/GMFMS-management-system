# Kerala location snapshot

This bundle contains 1 state, 14 districts, 152 Block Panchayats and 941 Grama Panchayats. It contains real institution records, not development demo fixtures. Counts in the application are queried from the database.

## Sources and verification

- [Kerala State Election Commission constituency directory](https://sec.kerala.gov.in/public/cnstncy): district lists, SEC Block and Grama Panchayat codes and English names.
- [LSGD local-body website directory](https://lsgkerala.gov.in/en/website/input/1/0): separate LSGD institution codes and names, across all 14 districts and all pages.
- [LSGD 2015 local-body hierarchy reference](https://lsgkerala.gov.in/htm/PDF/Election2015/Lcalbodies_2015.pdf): explicit District → Block → Panchayat relationships.

The SEC and LSGD directories were retrieved on 28 September 2026. The explicit hierarchy document is from **2015**; this bundle is not a claim of government certification of boundaries as of 2026. All 941 proposed parent relationships derived from LSGD directory codes were checked against that document. No hierarchy discrepancies remained after reviewed spelling aliases. Refresh against subsequent official boundary notifications before production rollout.

SEC and LSGD use different code systems. Never treat the two as interchangeable. Application district abbreviations (TVM, KLM, etc.) are stable registry keys, not government-issued SEC codes.

Exact normalized name matches are supplemented by the explicit, bijective SEC-to-LSGD crosswalk in sec_lsg_crosswalk.json. Spelling differences against the PDF are recorded in hierarchy_spelling_aliases.json. Fuzzy suggestions were used for review only; the build accepts only exact matches or these explicit aliases. Missing contacts and Malayalam Block/Panchayat names remain blank rather than invented. The model and importer support adding verified values.

sources.json records each source URL and SHA-256 checksum plus the final CSV checksum. The seed command rejects a modified CSV. Raw downloaded source pages are retained locally under ignored artifacts/location-sources/. They are unnecessary for normal seeding.

## Load and update

~~~text
python manage.py seed_kerala_locations --dry-run
python manage.py seed_kerala_locations
python manage.py import_locations reviewed.csv --source "Official source URL" --dry-run
python manage.py import_locations reviewed.xlsx --source "Official source URL" --actor ADMIN_USERNAME --update
python manage.py resolve_location_jurisdictions
~~~

The seed automatically resolves existing exact district/block jurisdiction codes to foreign keys. Unknown or invalid assignments remain denied. Imports from the staff page require SUPER_ADMIN authorization; shell commands without --actor run as trusted system maintenance and are audited accordingly.

Use locations.csv or download the CSV column template from the import screen. UTF-8 CSV and single-sheet XLSX are supported, up to 5 MB and 5,000 rows. XLSX formulas are rejected; paste values. Repeated parent definitions must agree. The active column affects the Panchayat; edit parent activity in the management screens.

Imports create absent records. Existing changes require --update or the UI update checkbox. This is a patch, not a replacement: omitted records are never deleted. Include existing optional values when updating because blank cells clear those values. Codes and parent relationships cannot change through imports or forms; boundary reorganizations need an explicit reviewed data migration. A failure rolls back every row and its audit/history records. Dry runs save nothing.

The Panchayat district is normalized through its Block foreign key and exposed as district/district_id properties. Query it with block__district. This prevents storing contradictory district/block combinations.

## Source rebuild tools

scripts/fetch_location_sources.py downloads the directory pages; scripts/parse_location_sources.py produces exact-match data and review suggestions. scripts/build_kerala_dataset.py requires the downloaded PDF and layout-preserving hierarchy.txt extraction, verifies all mappings, then emits the CSV and manifest. PDF extraction uses pypdf as an optional research dependency; application runtime and seed/import commands do not need it or internet access.

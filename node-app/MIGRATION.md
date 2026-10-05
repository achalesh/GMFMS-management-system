# Migration rehearsal and staging checks

The Django source remains authoritative. No operational importer is enabled yet. `export_node_snapshot` reads the source in a database transaction and verifies uploaded files/card artifacts against stored SHA-256 values. The private snapshot retains original model fields, relationships, password hashes, review/audit records and binary artifacts. It excludes transient request budgets; it is a migration archive, not a complete database backup or session transfer.

From the repository root, with the Django environment loaded:

```
.venv\Scripts\python.exe manage.py export_node_snapshot --output node-app/var/migration-NEW-DATE
```

From node-app:

```
node scripts/assess-migration.js var/migration-NEW-DATE
```

Both commands refuse to overwrite an existing result. The assessment checks record counts, snapshot digest and each artifact digest. It contains counts and mapping blockers without applicant values. Keep snapshot.json private: it includes personal data, password hashes, verification tokens and documents. var/ is excluded from the Hostinger ZIP. Store backups through an access-controlled backup process; the snapshot itself is not encrypted. Freeze source writes and preserve a complete database/media backup for the final cutover.

The local rehearsal on 2026-10-05 preserved 1,195 records and five artifacts. Three blockers remain: compatibility for the issued Django card and verification URL, lossless mapping of the appointment ledger, and handling the Django session-owned draft. No records were imported or changed. New card issuance or token rotation is not an acceptable substitute for preserving existing records without an explicit cutover plan.

## Create the staging database

In Hostinger hPanel, open the hosting plan's Databases / Management page and create a separate MySQL database and user for staging. Record the full prefixed database/user names and the host shown by Hostinger. Keep the password private. Do not reuse a WordPress database or the current production database. Configure MYSQL_URL in the staging Web App environment; URL-encode special characters in the username/password. Local checks require remote access configured for the actual client IP, or run the check within the hosting environment. Do not assume localhost on your computer reaches Hostinger.

After schema initialization in staging, run `node scripts/check-mysql.js` there (or through a supported hosting build command). It checks schema version, utf8mb4, max_allowed_packet >= 8 MB, InnoDB tables, Malayalam round trip and transaction rollback. No probe is inserted until all tables are confirmed transactional. Errors never log credentials. Connection checks have not run against Hostinger because no staging database has been created yet.

A passing database check does not establish full application compatibility. Run the registration/approval/private-upload/card/export browser workflow against MySQL, test backup restoration, resolve the mapping blockers and reconcile each imported entity before switching the main domain.

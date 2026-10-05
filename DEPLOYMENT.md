# Production deployment — gramaswaraj.in

## Current status and hosting requirement

The user selected **gramaswaraj.in** (main domain) and Hostinger shared/managed Web Hosting. [Hostinger documents that Django requires VPS hosting](https://www.hostinger.com/support/which-programming-languages-and-frameworks-are-supported-at-hostinger/). The existing plan cannot run this application's Django/Gunicorn/PostgreSQL stack. This package targets an Ubuntu VPS with Docker Compose and host Nginx. No hosting purchase, DNS changes, certificate issuance or remote deployment has occurred. Keep existing hosting and DNS until the replacement has passed acceptance.

Docker and PostgreSQL are absent on the Windows development machine; the image build, Compose startup, Nginx configuration check and live restore drill must be run on a staging/VPS host before cutover. Local tests do not substitute for these checks.

## Included deployment files

Dockerfile runs as UID/GID 10001. docker-compose.yml starts private PostgreSQL 17 and Gunicorn behind loopback port 18000, with persistent database/media volumes. The release service is a one-shot migration tool. Credentials are separated into deploy/database.env (owner initialization), deploy/migration.env (schema owner) and deploy/web.env (restricted runtime role). Secrets, local SQLite data, artifacts and private uploads are excluded from image build context. Do not upload private_media through a public web file manager.

Nginx configuration terminates HTTPS, overwrites proxy headers, rejects unexpected Host values, limits request bodies, bypasses application response caching and does not expose private media. Access logs omit URI, query, referer and client addresses. Site error logging is disabled to avoid raw token-bearing URLs; use sanitized application logs and status/health monitoring. Review host-wide/CDN/hosting logs separately.

The application trusts X-Real-IP only from explicit direct-peer CIDRs. Compose uses 172.30.80.0/24 with gateway 172.30.80.1. If this subnet conflicts, change Compose's subnet/gateway and both trusted-proxy/forwarded-allow-IP settings together. Verify the actual peer address on the host. Never use a wildcard or expose Gunicorn directly. Django REST throttling uses the normalized direct client address, not an arbitrary forwarded chain.

## Stage and configure

1. Obtain a Linux VPS or choose a Python-compatible host. For this package use a supported Ubuntu release, Docker Engine/Compose plugin, Nginx, Certbot, GPG and util-linux/flock. Configure SSH keys and firewall access: SSH restricted to administrators, public ports 80/443, no public database or Gunicorn port. Do not install this stack into Hostinger shared hosting.
2. Put source at /opt/gramaswaraj, excluding .env, .venv, artifacts and private data. Configure release control (Git or immutable release archives); this development workspace currently has no Git repository.
3. Copy each deploy/*.env.example to its corresponding .env file. Set file permissions to 600. Generate independent strong database passwords and a stable Django secret. URL-encode database passwords in DATABASE_URL. The migration environment uses gmfms_owner; the web environment uses gmfms_app. Both use the same Django secret and origin. Replace SMTP placeholders with verified credentials. Keep owner credentials out of web.env.
4. Preview configuration privately with `docker compose config --quiet` (do not print expanded secrets into support logs). Build with `docker compose build`. Start only the database using `docker compose up -d database`.
5. Run the schema release with `docker compose run --rm release`. It applies migrations and the bundled Kerala master. Review master changes/source currency. Never run concurrent release jobs. There is no automatic migration on ordinary web startup.
6. Open a private database shell: `docker compose exec database psql -U gmfms_owner -d gmfms`. Run `CREATE ROLE gmfms_app LOGIN;` then `\password gmfms_app` to set the app password interactively (same password as web.env). Exit psql. Apply the supplied privileges with `docker compose exec -T database psql -v ON_ERROR_STOP=1 -U gmfms_owner -d gmfms < deploy/grants.sql`. Reapply grants after every migration. The runtime role has no owner credentials, schema privileges or audit update/delete privileges.
7. Start web: `docker compose up -d web`. Startup runs deploy checks, confirms migrations are current, collects static files, then starts Gunicorn. Database readiness and web readiness are separate. `/health/` is liveness; `/internal/ready/` checks database availability without disclosing exceptions and is blocked at Nginx.
8. Create the initial production administrator interactively using `docker compose exec web python manage.py create_initial_admin`. Do not assume local accounts or applications have been copied.

## Existing local data

The local installation already contains real records and private files. They are deliberately excluded from the Docker image. Before launch, decide whether to migrate those records or begin with a fresh registry. Preserve a backup of db.sqlite3, private_media and the stable secret securely. A SQLite-to-PostgreSQL migration must be rehearsed separately, including UUIDs, sequences, role assignments, consent, audit history, storage filenames and card versions; do not run an unreviewed dump/loaddata into the new production schema. No local data has been uploaded or discarded.

## HTTPS and DNS cutover

Inventory the existing website and preserve it before replacing the main domain. Preserve mail MX/TXT records. Prepare a certificate for gramaswaraj.in using DNS validation during staging, or an HTTP ACME bootstrap when DNS points to the new host. The supplied final Nginx file requires existing valid certificate files; do not enable it before certificate issuance. A temporary HTTP server may serve only /.well-known/acme-challenge/ from /var/www/certbot and return 503 for the rest.

Set the certificate paths and install deploy/nginx.conf.example into the host Nginx configuration. Run `nginx -t` before reload. Stage against the new IP with a hosts-file override or curl --resolve while DNS still serves the old website. Confirm HTTPS works, secure cookies, CSRF sign-in/form POST, correct client-IP budgets, media access and QR status. Only after acceptance switch the apex A record (and AAAA only if working IPv6 is configured) to the VPS. www is not included: add a certificate/explicit redirect if required. Confirm certificate auto-renewal with `certbot renew --dry-run`. Do not cache verification or authenticated pages in a CDN.

## Tests on the target host

Run `docker compose run --rm web python manage.py check --deploy --fail-level WARNING` and `docker compose ps`. Use a separate test database/service and config.settings.integration with TEST_DATABASE_URL for PostgreSQL tests; it creates test_gmfms_integration and requires a disposable test role with CREATEDB. Never run these tests with a production database credential. Execute the automated suite and add concurrent approval/transfer/ID issuance exercises on actual PostgreSQL before accepting real writes. SQLite tests cannot establish locking correctness.

Check SMTP reset mail delivery, scoped role access, public privacy, upload rejection, mobile registration, expiry behavior, approved identities, card PDFs and report downloads. Validate organization branding/signatory and production QR origin before printing cards. Existing cards encoded with localhost need newly issued versions after configuring the real origin. Verify no .env, database, artifacts or media path is publicly accessible. Keep rollback evidence and acceptance results.

## Encrypted backup and isolated restore

Configure deploy/backup.env.example as /etc/gramaswaraj/backup.env with a verified GPG encryption recipient and absolute backup directory. Install only the public backup key on production; keep a recoverable private key separately. Test recipient trust under the account running the service. `BACKUP_RECIPIENT=<fingerprint> BACKUP_DIR=/var/backups/gramaswaraj bash deploy/backup.sh` stops web to quiesce writes, takes a custom-format pg_dump and private-media tar, hashes the members, encrypts one archive, and restarts web if it was running. This causes a short maintenance outage. Stop any future background writers too. Temporary plaintext files use restrictive permissions and are removed on exit; filesystem secure erasure is not guaranteed. Ensure adequate protected temporary disk space.

Copy encrypted files and their checksums off-site daily. Retain 7 daily and 4 weekly copies as an initial policy, subject to organizational retention requirements; no automatic deletion is implemented. Back up configuration/secrets and release identifiers in a separate secure process. Alert on missing/failed backups. Encryption without a tested private key is not recoverability.

Restore drill: use a separate isolated VPS with fresh Compose volumes, no public DNS, and outbound mail disabled. Verify the outer sha256 checksum, decrypt with GPG into a protected directory, inspect archive members, extract and run `sha256sum -c SHA256SUMS`. Start only its database. Restore database.dump into the EMPTY database with `pg_restore --exit-on-error --no-owner --no-acl` as migration owner (stream through docker compose exec -T database). Do not run migrations first into that empty restore target. Create the restricted runtime role and apply grants.sql. Restore private-media.tar to the isolated private_media volume through the web container as UID 10001. Start web with the matching application release; verify migration state, user roles, audit history, row/file counts, private downloads, QR behavior and representative PDF/checksum integrity. Measure elapsed recovery time and the backup's data-loss interval. Retain drill evidence; never use live production as a restore test.

## Maintenance and upgrades

Install the supplied service/timer files after adapting /opt/gramaswaraj to the real path. Backup defaults to 03:30 and maintenance to 03:00 in the server's timezone. Enable timers only after successful manual runs and verified notifications. Backup and maintenance share a lock. Maintenance runs clearsessions, prune_security_records, prune_registration_drafts and expire_facilitators; it never deletes audit history. Configure external HTTPS uptime monitoring and alert delivery. Check disk/backup age, restart counts and certificate expiry. Docker restart policies do not restart merely unhealthy containers; alerts need an operator or explicit recovery policy.

Before upgrades: create and verify a backup, keep the previous immutable image/release, stop writes, build/test the candidate, run one release job, reapply database grants and start web. Retest health and core workflows. Rolling back code across incompatible migrations is unsafe: restore the matched database/media/release into an isolated target first, then plan cutover. Never use `docker compose down -v` on a live installation.

References: [Compose health-dependent startup](https://docs.docker.com/compose/how-tos/startup-order), [Gunicorn proxy and logging settings](https://docs.gunicorn.org/en/stable/settings.html).

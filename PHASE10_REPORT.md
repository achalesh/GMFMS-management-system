# Phase 10 — Deployment preparation

Target requested: gramaswaraj.in, main website, Hostinger. Confirmed plan: shared/managed Web Hosting. Status: deployment package prepared; LIVE DEPLOYMENT BLOCKED by hosting compatibility. Hostinger's supported-framework guide requires VPS hosting for Django. No purchase, server access, DNS edit, public deployment or real-data migration has occurred.

Added Dockerfile/.dockerignore, docker-compose.yml (PostgreSQL + non-root web + separate release job), production/migration/database environment examples, Nginx HTTPS configuration, Gunicorn configuration, start/release scripts, database grants, encrypted backup/maintenance scripts and systemd timers, readiness probe, PostgreSQL integration-test settings, and deploy regression tests. DEPLOYMENT.md covers initial setup, credentials, preserving current website/local data, HTTPS, DNS cutover, SMTP, backups/restore, maintenance and rollback.

Runtime changes: trust real client IP only from configured direct proxy CIDRs; strip untrusted forwarded chains; DRF throttles use normalized REMOTE_ADDR; reject wildcard proxy trust at deploy checks. Readiness returns generic DB status with no-store; ingress blocks the internal endpoint. Default trusted proxy list is empty, so local behavior remains fail closed.

Validation: application suite and static deployment-contract tests run locally; production checks, schema validation, lint/format and migration drift checked. Docker/Compose, Nginx and PostgreSQL servers are not installed here, so image build, container startup, PostgreSQL concurrency, real TLS/SMTP, and encrypted restore drills are not yet verified. Python tests and YAML parsing are not a substitute for those deployment checks.

Next decision: provide a Hostinger VPS or another Django-compatible host. Existing local real data must be backed up and an explicit migration decision recorded before launch. Phase 10 is not complete until target-host acceptance, backup restore and public cutover succeed.

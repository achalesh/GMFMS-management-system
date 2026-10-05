#!/bin/sh
set -eu
exec 9>/tmp/gramaswaraj-backup.lock
flock -n 9 || exit 0
# Run daily from the project root; runtime account cannot delete audit rows.
for command in clearsessions prune_security_records prune_registration_drafts expire_facilitators; do
    docker compose exec -T web python manage.py "$command"
done

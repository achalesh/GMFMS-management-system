#!/bin/bash
# Encrypted, quiesced database+media backup. Run from the project root on Linux.
set -euo pipefail
umask 077
: "${BACKUP_RECIPIENT:?Set the GPG recipient fingerprint}"
: "${BACKUP_DIR:?Set an absolute encrypted-backup destination}"
[[ "$BACKUP_DIR" = /* ]] || { echo "BACKUP_DIR must be absolute" >&2; exit 1; }
command -v gpg >/dev/null
command -v docker >/dev/null
exec 9>/tmp/gramaswaraj-backup.lock
flock -n 9 || { echo "Backup already running" >&2; exit 1; }
mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
work=$(mktemp -d)
was_running=$(docker compose ps --status running -q web)
cleanup() {
    # The temporary directory is created here, never supplied by an input.
    rm -rf -- "$work"
    if [[ -n "$was_running" ]]; then docker compose start web >/dev/null; fi
}
trap cleanup EXIT
# No web or external workers may write during this snapshot.
docker compose stop web
docker compose exec -T database sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$work/database.dump"
docker compose run --rm --no-deps -T web tar -C /data/private_media -cf - . > "$work/private-media.tar"
printf 'UTC=%s\nMedia and database captured while web stopped.\n' "$stamp" > "$work/manifest.txt"
(cd "$work" && sha256sum database.dump private-media.tar > SHA256SUMS)
output="$BACKUP_DIR/gramaswaraj-$stamp.tar.gpg"
tar -C "$work" -cf - . | gpg --batch --yes --encrypt --recipient "$BACKUP_RECIPIENT" --output "$output.partial"
mv "$output.partial" "$output"
sha256sum "$output" > "$output.sha256"
printf 'Encrypted backup created: %s\n' "$output"

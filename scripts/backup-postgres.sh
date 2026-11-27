#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="infrastructure/compose/docker-compose.yml"
ENV_FILE="${ENV_FILE:-.env}"
SECRET_FILE="infrastructure/compose/secrets/backup_encryption_key.txt"
OUT_DIR="backups/postgres"

if [ ! -f "$SECRET_FILE" ]; then
  echo "error: $SECRET_FILE not found (copy backup_encryption_key.txt.example and set a real passphrase)" >&2
  exit 1
fi

COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

mkdir -p "$OUT_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$OUT_DIR/${TIMESTAMP}.sql.gpg"

# calls `docker compose exec postgres pg_dump` -- see infrastructure/compose/docker-compose.yml's
# postgres service; POSTGRES_USER/POSTGRES_DB expand inside the container from its own
# environment, so this script needs no database credentials of its own. --no-owner
# --no-privileges: a real restore-into-a-disposable-target test (see docs/runbooks/
# backup-restore.md) failed without these -- pg_dump's default output includes `ALTER
# TABLE ... OWNER TO <live role>`, which errors out on any target that doesn't happen to
# have that exact role, defeating the point of restoring somewhere other than the live DB.
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gpg --symmetric --batch --yes --pinentry-mode loopback \
        --passphrase-file "$SECRET_FILE" --cipher-algo AES256 \
        -o "$OUT_FILE"

echo "Backup written: $OUT_FILE"

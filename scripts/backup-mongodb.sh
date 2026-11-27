#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="infrastructure/compose/docker-compose.yml"
ENV_FILE="${ENV_FILE:-.env}"
SECRET_FILE="infrastructure/compose/secrets/backup_encryption_key.txt"
OUT_DIR="backups/mongodb"

if [ ! -f "$SECRET_FILE" ]; then
  echo "error: $SECRET_FILE not found (copy backup_encryption_key.txt.example and set a real passphrase)" >&2
  exit 1
fi

COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

mkdir -p "$OUT_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$OUT_DIR/${TIMESTAMP}.archive.gpg"

# calls `docker compose exec mongodb mongodump` -- see infrastructure/compose/docker-compose.yml's
# mongodb service (--auth enabled by Task #93). Reads the root password from the same
# Compose secret file the mongodb container itself mounts, with the same tr -d '\r' guard
# used everywhere else in this repo against core.autocrlf CRLF-corrupting tracked secret
# templates (see infrastructure/monitoring/README.md).
"${COMPOSE[@]}" exec -T mongodb sh -c \
  'mongodump --archive --username "$MONGO_INITDB_ROOT_USERNAME" --password "$(cat /run/secrets/mongo_root_password | tr -d "\r")" --authenticationDatabase admin' \
  | gpg --symmetric --batch --yes --pinentry-mode loopback \
        --passphrase-file "$SECRET_FILE" --cipher-algo AES256 \
        -o "$OUT_FILE"

echo "Backup written: $OUT_FILE"

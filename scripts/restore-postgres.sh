#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

SECRET_FILE="infrastructure/compose/secrets/backup_encryption_key.txt"
RESTORE_IMAGE="postgres:16-alpine"
RESTORE_CONTAINER="${RESTORE_CONTAINER:-pizza-store-restore-postgres}"
RESTORE_DB="${RESTORE_DB:-restore_verify}"
RESTORE_PASSWORD="${RESTORE_PASSWORD:-restore-verify-only}"

usage() { echo "usage: $0 <backup-file.sql.gpg>" >&2; exit 1; }
[ $# -eq 1 ] || usage
BACKUP_FILE="$1"
[ -f "$BACKUP_FILE" ] || { echo "error: $BACKUP_FILE not found" >&2; exit 1; }
[ -f "$SECRET_FILE" ] || { echo "error: $SECRET_FILE not found" >&2; exit 1; }

# Restore always targets this disposable, throwaway Postgres container -- never the live
# "postgres" Compose service or its volume -- so a bad restore can never corrupt real data.
# No --rm here: the caller inspects/verifies the restored data, then removes it explicitly
# (see docs/runbooks/backup-restore.md), rather than this script tearing down on exit.
docker rm -f "$RESTORE_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$RESTORE_CONTAINER" \
  -e POSTGRES_PASSWORD="$RESTORE_PASSWORD" \
  -e POSTGRES_DB="$RESTORE_DB" \
  "$RESTORE_IMAGE" >/dev/null

echo "Waiting for disposable restore target to become ready..."
ready=0
for _ in $(seq 1 30); do
  if docker exec "$RESTORE_CONTAINER" pg_isready -U postgres -d "$RESTORE_DB" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "error: $RESTORE_CONTAINER never became ready" >&2
  exit 1
fi

gpg --decrypt --batch --yes --pinentry-mode loopback --passphrase-file "$SECRET_FILE" "$BACKUP_FILE" \
  | docker exec -i "$RESTORE_CONTAINER" psql -U postgres -d "$RESTORE_DB" -v ON_ERROR_STOP=1 -q

echo "Restored into disposable container: $RESTORE_CONTAINER (database: $RESTORE_DB)"
echo "Verify with: docker exec $RESTORE_CONTAINER psql -U postgres -d $RESTORE_DB -c '<query>'"
echo "Clean up with: docker rm -f $RESTORE_CONTAINER"

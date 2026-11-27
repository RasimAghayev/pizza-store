#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

SECRET_FILE="infrastructure/compose/secrets/backup_encryption_key.txt"
RESTORE_IMAGE="mongo:7"
RESTORE_CONTAINER="${RESTORE_CONTAINER:-pizza-store-restore-mongodb}"

usage() { echo "usage: $0 <backup-file.archive.gpg>" >&2; exit 1; }
[ $# -eq 1 ] || usage
BACKUP_FILE="$1"
[ -f "$BACKUP_FILE" ] || { echo "error: $BACKUP_FILE not found" >&2; exit 1; }
[ -f "$SECRET_FILE" ] || { echo "error: $SECRET_FILE not found" >&2; exit 1; }

# Restore always targets this disposable, throwaway MongoDB container -- never the live
# "mongodb" Compose service or its volume -- so a bad restore can never corrupt real data.
# No --auth here: this target only ever holds a just-restored copy for verification and is
# removed immediately after, so production-grade auth hardening does not apply to it.
docker rm -f "$RESTORE_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$RESTORE_CONTAINER" "$RESTORE_IMAGE" >/dev/null

echo "Waiting for disposable restore target to become ready..."
ready=0
for _ in $(seq 1 30); do
  if docker exec "$RESTORE_CONTAINER" mongosh --quiet --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
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
  | docker exec -i "$RESTORE_CONTAINER" mongorestore --archive

echo "Restored into disposable container: $RESTORE_CONTAINER"
echo "Verify with: docker exec $RESTORE_CONTAINER mongosh --quiet --eval '<expression>'"
echo "Clean up with: docker rm -f $RESTORE_CONTAINER"

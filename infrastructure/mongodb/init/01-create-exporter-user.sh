#!/usr/bin/env bash
set -euo pipefail

# Runs during the entrypoint's unauthenticated init phase (same phase that creates the
# MONGO_INITDB_ROOT_* user), before --auth is enforced for normal operation — so no
# credentials are needed to connect here. Creates a least-privilege monitoring user for
# mongodb-exporter (infrastructure/compose/docker-compose.yml) instead of reusing root.
EXPORTER_PASSWORD="$(cat /run/secrets/mongodb_exporter_password | tr -d '\r')"

mongosh admin --quiet --eval "
db.createUser({
  user: 'mongodb_exporter',
  pwd: '${EXPORTER_PASSWORD}',
  roles: [
    { role: 'clusterMonitor', db: 'admin' },
    { role: 'read', db: 'local' }
  ]
})
"

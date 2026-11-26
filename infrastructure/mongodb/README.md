# MongoDB

Audit records, activity logs, order event history, delivery tracking history, analytics documents.

## Local Compose service

Defined in `infrastructure/compose/docker-compose.yml`, on `data-net` only. The official
`mongo` image's top-level process starts as root — required by its own initialization step —
but `mongod` itself drops to the image's built-in non-root `mongodb` user during normal
operation. This is the image's documented behavior, not a gap; a custom `user:` override would
break its init sequence.

**Connect locally** (after `make up`):

```sh
mongosh "mongodb://${MONGO_INITDB_ROOT_USERNAME:-pizza_store}:<password>@localhost:${MONGO_PORT:-27017}"
```

The password is read by the container from
`infrastructure/compose/secrets/mongo_root_password.txt` (copied from the `.example` template,
not committed — see `infrastructure/compose/README.md`).

**Backup / restore**:

```sh
# Backup
docker compose -f infrastructure/compose/docker-compose.yml exec -T mongodb \
  mongodump --username ${MONGO_INITDB_ROOT_USERNAME:-pizza_store} --authenticationDatabase admin --archive > backup.archive

# Restore
docker compose -f infrastructure/compose/docker-compose.yml exec -T mongodb \
  mongorestore --username ${MONGO_INITDB_ROOT_USERNAME:-pizza_store} --authenticationDatabase admin --archive < backup.archive
```

> Status: Phase 2 — Compose service defined and healthy; collections/schemas arrive in Phase 6.

# Backup and restore

Real, destructive backup/restore procedure for PostgreSQL and MongoDB (Task #96, Phase 4).
Master prompt §16 (Infrastructure Acceptance Gate) requires backup/restore to be verified by
a real test, not a configuration review — this document records that test.

## How it works

- `scripts/backup-postgres.sh` / `scripts/backup-mongodb.sh` run `pg_dump` / `mongodump`
  inside the live `postgres` / `mongodb` Compose service via `docker compose exec`, pipe the
  output through `gpg --symmetric --cipher-algo AES256`, and write a timestamped,
  encrypted-at-rest file under `backups/<postgres|mongodb>/` (gitignored — backups are data,
  never committed).
- `pg_dump` runs with `--no-owner --no-privileges` so the dump is restorable into any target,
  not only one that happens to have the exact same role as the live database (see the real
  bug this caught, below).
- `scripts/restore-postgres.sh <file>` / `scripts/restore-mongodb.sh <file>` decrypt a backup
  and restore it into a **disposable, throwaway container** (`pizza-store-restore-postgres` /
  `pizza-store-restore-mongodb`) created fresh by the script — never into the live `postgres`
  / `mongodb` Compose service or its volume. A bad restore script can therefore never corrupt
  real data. The container is left running after the script exits so the caller can verify
  the restored data before removing it (`docker rm -f <container>`).
- The passphrase used for encryption/decryption is `infrastructure/compose/secrets/
  backup_encryption_key.txt`, a Compose secret (file-based, gitignored, `.example` template
  tracked) — not mounted into any service, since `gpg` runs on the host/CI runner, not inside
  the database containers.
- `.github/workflows/backup-restore-test.yml` runs this entire cycle in CI (on PRs touching
  the backup/restore scripts or the Compose file, and on manual dispatch) so the real test
  below is repeatable, not a one-time manual run.

## Real test performed (2026-11-26)

Executed manually against the local Docker Compose stack (`postgres` + `mongodb` services
only), then verified again in CI via `.github/workflows/backup-restore-test.yml` on this
Task's own PR.

1. **Seed.** Inserted one known row into a fresh `backup_verification` table in the live
   `postgres` service, and one known document into a fresh `backup_verification.docs`
   collection in the live `mongodb` service, each holding a unique marker string
   (`backup-restore-test-20261126T062546Z-15227`).
2. **Backup.** Ran `scripts/backup-postgres.sh` and `scripts/backup-mongodb.sh`. Both
   produced a non-empty, AES-256-encrypted file (`backups/postgres/20261126T063612Z.sql.gpg`,
   `backups/mongodb/20261126T063452Z.archive.gpg`).
3. **Restore.** Ran `scripts/restore-postgres.sh` / `scripts/restore-mongodb.sh` against
   those files. Each script created its own disposable container
   (`pizza-store-restore-postgres` on `postgres:16-alpine`, `pizza-store-restore-mongodb` on
   `mongo:7`) and restored into it — the live services were never touched during restore.
4. **Verify.** Queried the disposable containers directly:
   - `docker exec pizza-store-restore-postgres psql -U postgres -d restore_verify -c
     "SELECT note FROM backup_verification WHERE note='backup-restore-test-...';"` →
     returned the exact marker row.
   - `docker exec pizza-store-restore-mongodb mongosh --quiet --eval
     "db.getSiblingDB('backup_verification').docs.findOne({note: 'backup-restore-test-...'})"`
     → returned the exact marker document, including its original `_id`.
5. **Clean up.** Removed both disposable containers, dropped the seeded test
   table/collection from the live services, and brought the stack back down.

**Real bugs found and fixed during this test:**

1. The first Postgres restore attempt failed with `ERROR: role "pizza_store" does not exist`.
   `pg_dump`'s default output includes `ALTER TABLE ... OWNER TO pizza_store` (the live
   database's own role), which errors on any target that doesn't happen to have that exact
   role — exactly the kind of problem a real restore-into-a-different-instance test exists to
   catch, as opposed to a dry run against the same database. Fixed by adding `--no-owner
   --no-privileges` to the `pg_dump` invocation.
2. The first CI run of `.github/workflows/backup-restore-test.yml` failed with `psql: error:
   ... FATAL: the database system is shutting down`, immediately after `pg_isready` had
   reported the disposable restore container ready. Root cause: on a brand-new data
   directory, the official `postgres` image's entrypoint starts a temporary server to run
   init scripts, stops it, then starts the real server — `pg_isready` can report success
   during that temporary server's brief window, and locally the extra latency of `gpg`'s
   first-run `apk add gnupg` happened to mask this race, while CI's faster, pre-installed
   `gpg` did not. Fixed by waiting for "database system is ready to accept connections" to
   appear twice in the container's logs (the documented-correct readiness signal for this
   image) instead of relying on `pg_isready` alone.

MongoDB's restore passed on the first attempt with no equivalent issue (`mongorestore` does
not carry an owner-role concept, and the disposable MongoDB container runs no init scripts,
so it has no comparable double-start phase). Re-ran the full cycle after each fix; both
passed, confirmed again in `.github/workflows/backup-restore-test.yml`'s real CI run on this
Task's PR.

## Known limitations

- Log retention/rotation beyond each service's own defaults is out of scope here (tracked in
  Task #97, secret management document).
- The `backup_encryption_key` passphrase's own rotation/distribution process is documented in
  Task #97, not here.
- `mongodump`/`mongorestore` here operate on the whole instance (no `--db` filter), matching
  this project's single-tenant-per-environment model; a future multi-tenant backup strategy
  would need to revisit this.

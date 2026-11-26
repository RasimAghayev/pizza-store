# Scripts

Repository-wide helper scripts (seed, reset, health-check, release automation).

## Backup and restore (Task #96, Phase 4)

- `backup-postgres.sh` / `backup-mongodb.sh` — dump the live `postgres` / `mongodb` Compose
  service via `docker compose exec`, encrypt the output with `gpg --symmetric` (AES-256,
  passphrase from `infrastructure/compose/secrets/backup_encryption_key.txt`), and write a
  timestamped file under `backups/<postgres|mongodb>/` (gitignored).
- `restore-postgres.sh <file>` / `restore-mongodb.sh <file>` — decrypt a backup file and
  restore it into a disposable throwaway container, never the live service. See
  [`docs/runbooks/backup-restore.md`](../docs/runbooks/backup-restore.md) for the real
  backup → restore → verify test this was proven against, and
  `.github/workflows/backup-restore-test.yml` for the repeatable CI version of that test.

> Status: Phase 0 folder structure plus the Phase 4 backup/restore scripts above; the rest
> (seed, reset, health-check, release automation) is implementation not yet started.

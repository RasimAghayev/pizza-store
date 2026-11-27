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

## Synthetic dataset generator (Task #111, Phase 5)

- `dataset/generate.py` — generates a fully synthetic, 24-month, fixed-seed business dataset
  (eighteen JSON Lines entity files) for the pizza store domain. No Django dependency, runs
  standalone ahead of Phase 10's real schema. See
  [`dataset/README.md`](dataset/README.md) for usage, the full entity list, and the
  reproducibility/verification guarantees.
- `dataset/verify.py` — referential-integrity, financial-reconciliation,
  status-history-monotonicity, and volume-threshold checks against any generated output.

> Status: Phase 0 folder structure, the Phase 4 backup/restore scripts, and the Phase 5
> synthetic dataset generator above; the rest (seed-into-database, reset, health-check,
> release automation) is implementation not yet started — seeding a live database is
> Phase 10 scope, once real Django/Postgres models exist.

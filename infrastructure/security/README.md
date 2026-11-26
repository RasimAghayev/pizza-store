# Infrastructure Security

Secret management, container/image scanning configuration, network isolation rules.

- **Secret management**: [docs/security/secret-management.md](../../docs/security/secret-management.md)
  is the concrete inventory of every secret in this repository/Compose stack and how it is
  delivered; [ADR 0006](../../docs/adr/0006-security-architecture-baseline.md) fixes the
  conventions it follows.
- **Container/image scanning**: `.github/workflows/container-scan.yml` (Trivy),
  `.github/workflows/sast.yml` (CodeQL, Semgrep, Bandit), and
  `.github/workflows/secret-scan.yml` (gitleaks) — no scanner configuration lives under this
  directory; each workflow file is its own configuration.
- **Network isolation**: three Compose networks in `infrastructure/compose/docker-compose.yml`
  (`edge-net`, `data-net`, `monitoring-net`) — databases sit on `data-net`, never directly on
  `edge-net`; monitoring containers are dual-homed only where an exporter needs direct
  database access.

> Status: Phase 4 — secret management inventoried and documented; container/image scanning
> and network isolation implemented in Phase 2/3 (see above). RBAC, JWT lifecycle, and
> multi-tenant isolation remain ADR-0006-designed but not yet implemented (Phase 6/Phase 10).

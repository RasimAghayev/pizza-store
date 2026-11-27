# VPS Deployment

> Status: Phase 8 (Issue #157) — `infrastructure/compose/docker-compose.prod.yml` validated
> end to end on a real local stand-in host. Per master prompt §8, this is the one deployment
> target that must be fully working and tested, not just `--dry-run`-validated like Swarm
> (Issue #158) or Kubernetes (Issue #159). ADR 0007 fixes the concrete target: a single Ubuntu
> LTS host, 4 vCPU / 8 GB RAM / 100 GB SSD, Nginx terminating TLS via Let's Encrypt/certbot.

## Prerequisites

- An Ubuntu LTS host meeting ADR 0007's baseline (4 vCPU / 8 GB RAM / 100 GB SSD) with Docker
  Engine installed via the [current official apt steps](https://docs.docker.com/engine/install/ubuntu/)
  (`docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`,
  `docker-compose-plugin`) — not a distro package, which trails upstream releases.
- A real, publicly DNS-resolving domain pointed at the host (required for real Let's Encrypt
  issuance — see SSL below for why this Task's own validation substitutes a locally-trusted
  CA instead of exercising real issuance).
- `backend`/`frontend` images already built: `docker compose -f
  infrastructure/compose/docker-compose.yml build backend frontend`, or pulled from a
  registry if this host does not build them itself.
- Repo cloned/copied onto the host; `infrastructure/compose/secrets/*.txt` and `.env`
  populated from their `.example` templates with real values (never the placeholders).

## Environment

Two independent, deliberately separate mechanisms control what runs, per current (2026)
Docker Compose guidance (profiles select optional services; they are not an
environment-override mechanism) — researched and confirmed against Docker's own docs before
implementing, per this repo's research-before-implementing rule:

- **`profiles:`** — the Phase 4 monitoring/logging/tracing/alerting stack (`prometheus`,
  `alertmanager`, `grafana`, the three exporters, `loki`, `promtail`, `jaeger`,
  `otel-collector` — 10 services) carries `profiles: ["observability"]` in
  `docker-compose.yml`. The seven core serving services (`postgres`, `mongodb`, `redis`,
  `rabbitmq`, `backend`, `frontend`, `nginx`) carry no profile and always start.
  `COMPOSE_PROFILES=observability` in `.env.example` keeps the profile on by default, so local
  dev/CI behavior is unchanged from before profiles existed. A resource-constrained VPS can
  set `COMPOSE_PROFILES=` (empty) to run only the core stack.
- **`docker-compose.prod.yml`** — a merge-only override, never standalone, for genuinely
  environment-specific config profiles are not meant to carry: TLS-terminating Nginx and
  certificate issuance/renewal (see Networking/SSL below).

```sh
docker compose -f infrastructure/compose/docker-compose.yml \
  -f infrastructure/compose/docker-compose.prod.yml \
  --env-file .env up -d
```

## Secrets

Unchanged from the base Compose stack — every credential is a Docker secret (`file:` source
under `infrastructure/compose/secrets/`), never a plain environment variable. No new secret
mechanism is introduced for the VPS target: `docker-compose.prod.yml` adds no `secrets:` of
its own (the `certbot` service's `CERTBOT_DOMAIN`/`CERTBOT_EMAIL` are not credentials — a
domain name and a contact address, both already public once DNS/WHOIS exist). Certificate/key
material issued by certbot is never committed to the repo (Security Requirements) — it lives
in the `certbot-etc`/`nginx-ssl` named volumes, created fresh on the host, never checked in.

## Networking

`docker-compose.prod.yml` overrides the base `nginx` service's `volumes:` at the same
container mount path (`/etc/nginx/conf.d`) — Compose merges `volumes:` entries by container
path, not by list position — swapping `infrastructure/nginx/conf.d/default.conf` for
`infrastructure/nginx/conf.d.prod/prod.conf`. The two must never load together: both declare
`server_name _;` on port 8080, and nginx rejects duplicate default servers. `ports:` entries
concatenate (Compose's documented merge rule for `ports`), so the base file's HTTP port
mapping and the override's new HTTPS port mapping both apply.

`prod.conf` adds:

- A `listen 8443 ssl;` server block proxying the same `/api/` → `backend:8000` and `/` →
  `frontend:8080` routes as `default.conf`, terminating TLS.
- Port 8080 becomes an HTTP→HTTPS redirect, except `/.well-known/acme-challenge/`, which
  serves certbot's webroot challenge directory directly (current certbot guidance: `--webroot`
  keeps certbot from touching nginx's own config, unlike `--nginx`).

## Database setup

No VPS-specific steps beyond the base Compose stack — `postgres`/`mongodb`/`redis`/`rabbitmq`
are unaffected by `docker-compose.prod.yml`, which touches only `nginx` and adds `certbot`.

## Backup/Restore

Unchanged — see `docs/runbooks/backup-restore.md`. `scripts/backup-postgres.sh`/
`backup-mongodb.sh` run against the same `postgres`/`mongodb` Compose services regardless of
which override file is also in play.

## SSL

Real production issuance uses the `certbot` service added by `docker-compose.prod.yml`:
HTTP-01 webroot challenge against `CERTBOT_DOMAIN`, sharing the `certbot-www` volume with
nginx's `/.well-known/acme-challenge/` location. Because nginx's `ssl_certificate` path in
`prod.conf` is a **fixed** location (`/etc/nginx/ssl/{fullchain,privkey}.pem`) independent of
any domain name, certbot's own entrypoint command copies the real issued cert from
`/etc/letsencrypt/live/$CERTBOT_DOMAIN/` into that fixed path after issuance and again after
every renewal (a `--deploy-hook`), so nginx's config never needs to know the real domain name.

**Real VPS bootstrap order** (first deployment only): nginx's HTTPS server block needs a
certificate file to exist before nginx will even start — a well-known certbot/nginx
chicken-and-egg problem. Bring the stack up once with only the HTTP-01 challenge path reachable
(core services + nginx, `certbot` started after, or a temporary self-signed placeholder), let
`certbot` complete its first `certonly` run and populate `/etc/nginx/ssl/`, then restart
`nginx` so it picks up the real certificate.

**Why this Task's own test does not exercise real issuance**: the real test below runs
against a disposable local stand-in host with no public DNS record — Let's Encrypt's HTTP-01
challenge cannot reach a host the public internet cannot route to, staging or production CA.
Per the Issue's own Technical Context, this Task's real TLS validation uses
[mkcert](https://github.com/FiloSottile/mkcert) (a locally-trusted CA) instead of skipping SSL
validation entirely: a real certificate chain is generated, installed, and verified end to end
against the stand-in host's own nginx — the `certbot` service itself is a genuine deliverable
for real VPS use but was **not started** during this validation (documented honestly, not
silently skipped — see Validation evidence below).

## Reverse proxy

`nginx` behavior is otherwise unchanged from the base Compose stack (`default.conf`'s
`/healthz`, `/api/` → backend, `/` → frontend routing) — `prod.conf` only adds the TLS/redirect
wrapper around the same routes.

## Monitoring / Logging

Unchanged from Phase 4 — gated behind the `observability` Compose profile (see Environment
above), not anything VPS-specific. A resource-constrained single VPS can disable this profile
entirely; the real validation below ran with it enabled, matching local dev/CI's default.

## Scaling

A single VPS has no orchestrator-level horizontal scaling (that is what the Swarm/Kubernetes
targets are for, ADR 0007) — `docker compose up --scale backend=<n>` is available for the
stateless `backend`/`frontend` services, but is not exercised by this Task.

## Rollback

`restart: unless-stopped` (already set on every service in the base file, not re-declared by
the override) restarts a crashed container automatically. A bad deploy is rolled back by
re-pulling/re-building the previous image tag and re-running `docker compose up -d` — no
rolling-update mechanism exists for a single-host Compose deployment (unlike Swarm's
`update_config.failure_action: rollback`); documented as a real, named gap of this target, not
silently assumed away.

## Disaster recovery

A single VPS is a single point of failure for the entire stack, including its own control
plane — there is no redundancy at this deployment target by design (ADR 0007 positions VPS as
the baseline target, not the resilient one). Backup/restore (above) covers data recovery onto
a replacement host; host-level redundancy is Swarm's or Kubernetes' job, not this Task's.

## Security hardening

TLS 1.2+ only (`prod.conf`'s `ssl_protocols TLSv1.2 TLSv1.3;`), no plaintext HTTP origin
traffic once `docker-compose.prod.yml` is active (port 8080 redirects to HTTPS, it never
serves the app directly). Cipher suite, session-cache, and ticket settings match the current
(2026) [TLSRef/Mozilla "Intermediate" server-side-TLS profile](https://docs.tlsref.org/server-side-tls.html)
for nginx (TLS 1.2 + 1.3, client chooses cipher preference). Every credential remains a Docker
secret; certificate/key material is never committed.

## Troubleshooting

**nginx fails to start with "cannot load certificate" after first deploying
`docker-compose.prod.yml`.** The chicken-and-egg bootstrap problem described under SSL above —
`/etc/nginx/ssl/fullchain.pem` does not exist yet on a brand-new host. Either pre-seed that
volume with a certificate (as this Task's own test does with mkcert) or follow the two-phase
real bootstrap order under SSL.

**`docker compose config` warns about an unset variable when only
`docker-compose.yml` is used.** `CERTBOT_DOMAIN`/`CERTBOT_EMAIL`/`NGINX_HTTPS_PORT` are only
read by `docker-compose.prod.yml`; `.env.example` sets safe placeholders for all three so this
never actually happens, but if a real `.env` drops them, add them back from `.env.example`.

**nginx still fails to start with "cannot load certificate key ... Permission denied" even
though the certificate files exist.** `nginx` runs as the `nginxinc/nginx-unprivileged` image's
non-root user, and a plain `cp` out of `/etc/letsencrypt/live/...` preserves certbot's
root-only `0600` mode on `privkey.pem`. `docker-compose.prod.yml`'s `certbot` service already
`chmod 644`s both files after every copy (first issuance and each renewal); if a certificate
was placed into the `nginx-ssl` volume by some other means (manual copy, a different script),
it needs the same `chmod`.

**nginx reports `unhealthy` in `docker compose ps` even though `curl`ing it manually works
fine.** Only happens once `docker-compose.prod.yml` is active — the base healthcheck probes
plain HTTP on 8080, which the prod override turns into an HTTPS redirect (a bodyless `301`,
not the `200` the healthcheck expects). `docker-compose.prod.yml` overrides the `nginx`
healthcheck to probe `https://localhost:8443/healthz` instead; if this ever regresses, check
`docker compose config` resolves exactly one `healthcheck:` for `nginx` (the override's).

## Validation evidence (2026-11-27)

Real local stand-in host: a privileged, systemd-enabled Ubuntu 24.04 Docker container
(`jrei/systemd-ubuntu:24.04`) with a genuine, separately installed Docker Engine inside it
(official apt steps above) — a disposable, nested "bare host," not this development
container/the CI runner, satisfying the Epic's "a real VPS or an equivalent test environment"
requirement. Backend/frontend images built earlier in this session were transferred in via
`docker save`/`docker load` (no rebuild needed); `postgres`/`mongodb`/`redis`/`rabbitmq`/
`nginx`/the observability-stack images were pulled fresh from their public registries by the
nested engine, exactly as a real VPS's first deploy would.

All 17 services from `docker compose -f docker-compose.yml -f docker-compose.prod.yml config
--services` (minus `certbot`, not started — see SSL above) came up; all 12 of them that carry a
Compose `healthcheck:` reported `healthy` (the other five — `loki`, `promtail`,
`otel-collector`, `mongodb-exporter`, `redis-exporter` — are scratch/distroless images with no
shell, so they carry no `CMD-SHELL` healthcheck by design, documented in
`docker-compose.yml` itself):

```
pizza-store-alertmanager-1        Up 7 minutes (healthy)
pizza-store-backend-1             Up 6 minutes (healthy)
pizza-store-frontend-1            Up 7 minutes (healthy)
pizza-store-grafana-1             Up 7 minutes (healthy)
pizza-store-jaeger-1              Up 7 minutes (healthy)
pizza-store-loki-1                Up 7 minutes
pizza-store-mongodb-1             Up 7 minutes (healthy)
pizza-store-mongodb-exporter-1    Up 7 minutes
pizza-store-nginx-1               Up 25 seconds (healthy)
pizza-store-otel-collector-1      Up 6 minutes
pizza-store-postgres-1            Up 7 minutes (healthy)
pizza-store-postgres-exporter-1   Up 7 minutes (healthy)
pizza-store-prometheus-1          Up 7 minutes (healthy)
pizza-store-promtail-1            Up 7 minutes
pizza-store-rabbitmq-1            Up 7 minutes (healthy)
pizza-store-redis-1               Up 7 minutes (healthy)
pizza-store-redis-exporter-1      Up 7 minutes
```

Real HTTPS request against nginx's own TLS listener, verified with the mkcert root CA (no
`-k`/`--insecure`):

```
$ curl -i --cacert rootCA.pem https://localhost:8443/healthz
HTTP/1.1 200 OK
Server: nginx/1.27.5
Content-Type: text/plain
Content-Length: 3

ok
```

Real HTTP→HTTPS redirect on port 8080:

```
$ curl -i http://localhost:8080/healthz
HTTP/1.1 301 Moved Permanently
Server: nginx/1.27.5
Location: https://localhost/healthz
```

(`Location` omits the port because port 443 is the implicit default for `https://` — correct
for a real deployment; this stand-in host maps the container's 8443 to a non-standard host
port purely so it coexists with other local services, which is why manually hitting
`https://localhost:8443/healthz` is required to actually follow it here.)

Real TLS chain verification with `openssl s_client`, confirming the full chain validates
against the mkcert root CA:

```
$ echo | openssl s_client -connect localhost:8443 -CAfile rootCA.pem
subject=O = mkcert development certificate, OU = root@<host>
issuer=O = mkcert development CA, OU = root@<host>, CN = mkcert root@<host>
Verify return code: 0 (ok)
```

**Two real defects this test caught and fixed** (neither would have surfaced from a
`--dry-run`/`config` check — the reason this Task requires a genuine running stack):

1. **Certificate key permissions.** `nginx` runs as the `nginxinc/nginx-unprivileged` image's
   non-root user, but `cp`-ing a cert/key out of `/etc/letsencrypt/live/...` preserves
   Certbot's root-only `0600` mode on `privkey.pem`. nginx failed to start
   (`cannot load certificate key ... Permission denied`) until the copy was followed by
   `chmod 644` — now baked into `docker-compose.prod.yml`'s `certbot` service for both the
   first-issuance copy and the renewal `--deploy-hook`, so a real production deploy hits the
   same fix, not just this test's substitute mkcert cert.
2. **Healthcheck broken by the HTTPS redirect.** The base `nginx` healthcheck
   (`wget --spider http://localhost:8080/healthz`) is correct without `docker-compose.prod.yml`,
   but once the prod override turns port 8080 into an HTTP→HTTPS redirect, that same probe
   gets a bodyless `301` instead of a `200` and nginx reports `unhealthy` forever, even while
   correctly serving traffic. `docker-compose.prod.yml` now overrides `nginx`'s healthcheck to
   probe `https://localhost:8443/healthz` instead (`--no-check-certificate`, since a liveness
   probe's job is reachability, not trust, and the cert may be a real Let's Encrypt cert or a
   local-only one depending on environment).

Teardown: `docker compose ... down -v` inside the stand-in host, then the stand-in host
container itself removed — no lingering state on the real machine that ran this test.

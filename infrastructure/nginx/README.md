# Nginx

Reverse proxy configuration, SSL termination, routing.

## Local Compose service

Defined in `infrastructure/compose/docker-compose.yml`, on `edge-net` only — never `data-net`,
so Nginx has no network route to any database or broker. Uses
`nginxinc/nginx-unprivileged:1.27-alpine` rather than the official `nginx` image, since the
official image needs root to bind port 80; the unprivileged variant listens on 8080
internally by design. The host-side port mapping still exposes it as `${NGINX_HTTP_PORT}`
(80 by default), so this is transparent to anything hitting `http://localhost`.

`infrastructure/nginx/conf.d/default.conf` serves `/healthz` (used by the Compose
healthcheck), proxies `/api/` to `backend:8000`, and proxies everything else to
`frontend:8080` — unifying both under one origin so browser-mode cookie auth's
`SameSite=Strict` cookies are attached (Issue #140).

The config explicitly declares both `listen 8080;` and `listen [::]:8080;`. The image's own
entrypoint normally auto-patches `conf.d/default.conf` to add IPv6 listening, but it cannot
since the directory is mounted read-only (`:ro`) — without the explicit IPv6 listener, the
Compose healthcheck's own `wget http://localhost:8080/healthz` resolves `localhost` to `::1`
first inside the container's network namespace and gets connection-refused, even though the
service is reachable fine from the host (Docker's port-forwarding masks the gap from outside).

**Verify locally** (after `make up`):

```sh
curl http://localhost:${NGINX_HTTP_PORT:-80}/healthz
```

**Non-root**: `docker compose -f infrastructure/compose/docker-compose.yml exec nginx whoami`
should report a non-root user.

## VPS deployment (TLS)

`infrastructure/nginx/conf.d.prod/prod.conf` is a separate, prod-only config — mounted by
`infrastructure/compose/docker-compose.prod.yml` at the same container path
(`/etc/nginx/conf.d`) in place of `conf.d/default.conf`, never alongside it, since both
declare `server_name _;` on port 8080 and nginx rejects duplicate default servers. It adds a
`listen 8443 ssl;` server block (TLSRef/Mozilla "Intermediate" TLS 1.2/1.3 profile) and turns
port 8080 into an HTTP→HTTPS redirect plus the `/.well-known/acme-challenge/` location
certbot's webroot challenge needs. Real certificate issuance/renewal is the `certbot` service
in `docker-compose.prod.yml` — see `docs/deployment/vps.md`'s SSL section for the full
bootstrap procedure and this Task's real validation evidence.

> Status: Phase 8 (Issue #157) — done. Real upstreams (Phase 6/7) and TLS (this Task) both in
> place.

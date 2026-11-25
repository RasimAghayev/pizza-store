# Nginx

Reverse proxy configuration, SSL termination, routing.

## Local Compose service

Defined in `infrastructure/compose/docker-compose.yml`, on `edge-net` only — never `data-net`,
so Nginx has no network route to any database or broker. Uses
`nginxinc/nginx-unprivileged:1.27-alpine` rather than the official `nginx` image, since the
official image needs root to bind port 80; the unprivileged variant listens on 8080
internally by design. The host-side port mapping still exposes it as `${NGINX_HTTP_PORT}`
(80 by default), so this is transparent to anything hitting `http://localhost`.

`infrastructure/nginx/conf.d/default.conf` currently only serves `/healthz` (used by the
Compose healthcheck) and a placeholder `503` on `/`, since there is no backend/frontend
container to proxy to yet. Phase 6/7 replace the `/` location with real `proxy_pass`
directives once those containers exist.

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

Real TLS/Let's Encrypt is the VPS deployment target's responsibility (ADR 0007, Phase 8), not
this local Compose stack's.

> Status: Phase 2 — Compose service defined and healthy; real upstreams arrive in Phase 6/7.

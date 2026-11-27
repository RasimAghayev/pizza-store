# Kubernetes Deployment

> Status: Phase 8 (Issue #159) — `infrastructure/kubernetes/helm/pizza-store/` validated end
> to end on a real local `kind` cluster. Per ADR 0007, this is the second deployment target
> built (after Docker Swarm, Issue #158); the Compose/Swarm stack remains the translation
> reference, and several translation pitfalls caught during Swarm's own build (healthchecks,
> network segmentation) reappeared here in a Kubernetes-specific form — documented below
> rather than silently fixed.

## Prerequisites

- A Kubernetes cluster — this Task validates against a local
  [`kind`](https://kind.sigs.k8s.io/) (Kubernetes IN Docker) cluster, not a managed cloud
  cluster (see [`docs/cloud/`](../cloud/) for the AWS/GCP/Azure managed-Kubernetes story).
- [Helm](https://helm.sh/) v3/v4 (Chart API `v2`) and `kubectl` matching the cluster's minor
  version.
- `backend`/`frontend` images already built locally (same images the Compose/Swarm validation
  used): `docker compose -f infrastructure/compose/docker-compose.yml build backend frontend`.
  Against `kind`, load them into the cluster's containerd with no registry needed:
  `kind load docker-image pizza-store-backend:latest pizza-store-frontend:latest --name
  <cluster-name>`. Against a real cluster, push to a registry and set
  `values.yaml`'s `images.*.repository` accordingly.
- An [ingress-nginx](https://kubernetes.github.io/ingress-nginx/) controller pre-installed on
  the cluster. This chart's `templates/ingress.yaml` assumes it (`className: nginx`) but does
  not install it — a cluster-level concern out of this chart's scope, same reasoning Issue
  #158 used to leave TLS termination to the VPS target (Issue #157).

## Environment

Unlike Swarm's `${VAR}` shell-environment substitution (see `docs/deployment/swarm.md`'s
Environment section), Helm's templating reads entirely from `values.yaml` plus any `--set`/
`-f` overrides at install time — there is no separate `.env` file to export. Install with the
shipped placeholder values (safe defaults, `helm lint`/`helm template` succeed with zero real
input):

```sh
helm install pizza-store infrastructure/kubernetes/helm/pizza-store \
  --namespace pizza-store --create-namespace
```

A real deployment overrides `values.yaml`'s `secrets.*` and `djangoCorsAllowedOrigins` via a
separate, gitignored values file (`-f my-real-values.yaml`) or `--set`, the same way Compose's
`infrastructure/compose/secrets/*.txt` are gitignored and never committed.

## Secrets

All ten credential values (`postgresPassword`, `mongoRootPassword`, `redisPassword`,
`rabbitmqPassword`, `djangoSecretKey`, `jwtPrivateKey`, plus the four non-secret identity
values `postgresDb`/`postgresUser`/`mongoRootUsername`/`rabbitmqUser`) live in
`values.yaml`'s `secrets:` block and are rendered into a single Kubernetes `Secret`
(`templates/secret.yaml`) via `stringData`. This mirrors Swarm's `secrets:` top-level block
conceptually (one declared secret object per credential) but not mechanically — Kubernetes
`Secret` values are base64-encoded at rest, not file-mounted, so the backend Deployment
consumes them via `env.valueFrom.secretKeyRef` rather than reading a mounted file path the way
the Compose/Swarm backend does.

## Networking

Every Service is `ClusterIP` (no component needs a stable identity beyond cluster-internal
DNS); `nginx`'s two replicas sit behind a `ClusterIP` Service fronted by the Ingress resource,
the Kubernetes equivalent of Swarm's ingress routing mesh. `NetworkPolicy` resources recreate
the Compose/Swarm `edge-net`/`data-net` segmentation:

- `templates/netpol-default-deny.yaml` — namespace-wide default-deny on ingress (`podSelector:
  {}`), so nothing is reachable unless an explicit allow policy below grants it.
- `templates/netpol-allow-edge.yaml` — anything may reach `nginx` (it is the cluster's entry
  point); `frontend` and `backend` accept traffic only from `nginx`.
- `templates/netpol-allow-data.yaml` — `postgres`/`mongodb`/`redis`/`rabbitmq` accept traffic
  only from `backend`.

**Real, non-obvious gap found during this validation**: `kind`'s default CNI (`kindnet`) does
**not enforce** `NetworkPolicy` at all — policies apply cleanly with `kubectl apply` but every
Pod stays mutually reachable regardless, which would have made the proof below pass
meaninglessly even with a real connectivity bug in the policies. Fixed by creating the `kind`
cluster with `networking.disableDefaultCNI: true` and a non-default `podSubnet:
192.168.0.0/16`, then installing [Calico](https://docs.tigera.io/calico/latest/) (CRDs,
`tigera-operator`, `custom-resources`, pinned to v3.33.0 for the cluster's Kubernetes 1.37
node image) before deploying the chart. A managed cluster's own CNI (e.g. AWS EKS's VPC CNI
with Calico/Cilium add-on, GKE's Dataplane V2, AKS's Azure CNI with Calico/Cilium) must be
confirmed to enforce `NetworkPolicy` the same way — it is not a given for every CNI, as this
`kind` default proved.

## Database setup

No database-specific Kubernetes steps beyond what the Compose/Swarm stacks already do —
`postgres`/`mongodb`/`redis`/`rabbitmq` use the exact same images, init env vars, and
healthcheck logic. Each is a `StatefulSet` with `replicas: 1` (same reasoning as Swarm's
`replicas: 1` constraint — no built-in multi-replica coordination for these engines at this
project's scope) and a `volumeClaimTemplate` giving each its own `PersistentVolumeClaim`.

**Real translation bug caught before any cluster testing**: the `postgres` and `mongodb`
StatefulSets were first written using Kubernetes' `command:` field to carry over
Swarm/Compose's `command:` key verbatim. Kubernetes' `command` field overrides a container's
Docker **ENTRYPOINT**, while Compose/Swarm's `command:` key only ever replaces **CMD** — these
are not equivalent despite the identical YAML key name. Both images' real entrypoint scripts
(`docker-entrypoint.sh`) perform `initdb`/root-user setup from env vars; overriding
`ENTRYPOINT` would have silently skipped that setup. Fixed by using Kubernetes' `args:` field
instead, which only replaces CMD — the correct translation target.

## Backup/Restore

Unchanged from `docs/runbooks/backup-restore.md` in mechanism — `scripts/backup-postgres.sh`/
`backup-mongodb.sh` need only target the right Pod (`kubectl exec -n pizza-store
statefulset/postgres -- ...` instead of a Compose service name or a Swarm task filter). The
dump/restore logic itself is image/engine-specific, not orchestrator-specific, so it does not
change between Compose, Swarm, or Kubernetes.

## SSL

Out of scope for this Task, same as Swarm (Issue #158) — TLS termination is the VPS
deployment's responsibility (Issue #157, ADR 0007). On a real Kubernetes cluster, TLS would
terminate at the Ingress controller (e.g. `cert-manager` issuing certificates for the
`Ingress` resource) rather than inside this chart.

## Reverse proxy

`nginx` is replicated at 2 and reachable in-cluster via its `ClusterIP` Service; the
`Ingress` resource (`templates/ingress.yaml`, `className: nginx`, host
`values.yaml`'s `ingress.host`) routes external HTTP to it, assuming the ingress-nginx
controller from Prerequisites. `templates/configmap-nginx.yaml` mirrors
`infrastructure/nginx/conf.d/default.conf` verbatim (templated), so the `/api/` routing rule to
`backend` and the SPA fallback for `frontend` behave identically to the already-validated
Compose/Swarm setup.

## Monitoring

Not part of this chart — the observability stack (Prometheus/Grafana/Loki/Promtail, Phase 4)
is a separate concern not yet translated to Kubernetes. Deferred, same as Phase 4's own
Compose-only scope; revisit if a future Epic needs cluster-native observability
(`kube-prometheus-stack` or equivalent).

## Logging

Container stdout/stderr is captured by the kubelet/container runtime on every node by default
(`kubectl logs`) — no equivalent to Swarm's `promtail` `global`-mode DaemonSet is deployed by
this chart. Same deferral as Monitoring above.

## Scaling

`templates/hpa.yaml` defines two `HorizontalPodAutoscaler` objects (`backend`: 2-5 replicas,
`frontend`: 2-4 replicas, both CPU-target 70%) — unlike Swarm, which only allows manual
`docker service scale`, Kubernetes can scale these automatically based on real load. Stateful
services are intentionally not horizontally scaled, same reasoning as Database setup above.

## Rollback

Each Deployment uses `strategy.type: RollingUpdate` with `maxUnavailable: 0` (no capacity
drop during a rollout). A failed rollout can be reverted with `kubectl rollout undo
deployment/backend -n pizza-store` or `helm rollback pizza-store <revision>` for a full
chart-level revert — not exercised as a failure case in this validation (the real
`helm upgrade` performed below, to fix the backend probe issue, succeeded), but both
mechanisms are standard Kubernetes/Helm behavior, not custom to this chart.

## Disaster recovery

A single-node `kind` cluster is a single point of failure for the cluster's own control
plane, same category of gap Swarm's single-manager validation documented — out of scope for
this local validation. A production-grade cluster (managed, e.g. EKS/GKE/AKS per
`docs/cloud/comparison.md`, or self-managed with multiple control-plane nodes) is required to
close this gap; not solved by this Task.

## Security hardening

Every credential is a Kubernetes `Secret`, never a plain environment variable value baked
into a template; `NetworkPolicy` segmentation is enforced (not just declared) and was proven
via the timing-based test below, once the real `kind`-default-CNI gap (Networking, above) was
closed. Probe configuration was hardened to avoid two different failure modes documented
below (Troubleshooting), rather than loosening application-level config to work around them.

## Troubleshooting

**Backend Pods `CrashLoopBackOff` with repeated `400` responses in `kubectl logs`.** A real
failure hit during this validation: `kubectl logs` showed `"GET /health/ HTTP/1.1" 400 143`
on every probe request. Root cause: Kubernetes' kubelet issues `httpGet` probes directly
against the Pod's IP address with the HTTP `Host` header set to that same IP — **not**
`localhost`, unlike `curl`'s healthcheck in the already-validated Compose/Swarm setup. Django's
`ALLOWED_HOSTS` (`backend/config/settings.py`, defaulting to `localhost,127.0.0.1`) then
rejects the probe request with `400`, and the kubelet restarts the container believing it is
unhealthy. Fixed without touching Django config: added `httpHeaders: [{name: Host, value:
localhost}]` to both `livenessProbe.httpGet` and `readinessProbe.httpGet` in
`templates/deployment-backend.yaml`, which makes kubelet send `Host: localhost` explicitly —
reproducing curl's exact real-world behavior rather than loosening `ALLOWED_HOSTS`.

**`NetworkPolicy` resources apply cleanly but connectivity is unaffected.** Confirm the
cluster's CNI actually enforces `NetworkPolicy` — see the real `kind`-default-CNI gap under
Networking above. `kubectl get networkpolicy -n pizza-store` succeeding is not evidence of
enforcement; test an actual blocked path (see Validation evidence below) before trusting the
declared policy.

**`kubectl apply --dry-run=client` fails with a `dial tcp 127.0.0.1:8080` connection error.**
Current `kubectl` (1.37.x) needs live API-server access to download OpenAPI schema even in
client-dry-run mode — this is not an offline check. Run it against a real (even if local/
disposable) cluster instead of expecting a fully offline validation.

## Validation evidence (2026-11-27)

Real local `kind` cluster (`pizza-store-validation`, Calico CNI, default CNI disabled,
`podSubnet: 192.168.0.0/16`), chart installed via `helm install`/`helm upgrade` into the
`pizza-store` namespace:

- All 10 Pods (2× `backend`, 2× `frontend`, 2× `nginx`, 1× `postgres`, 1× `mongodb`, 1×
  `redis`, 1× `rabbitmq`) reached `Running`/`Ready`, `0` restarts, after the backend probe fix
  above (`helm upgrade pizza-store infrastructure/kubernetes/helm/pizza-store -n
  pizza-store`, revision 2).
- `kubectl apply --dry-run=client -f <rendered manifest>` against the live cluster: every
  resource reported `created (dry run)`, exit code `0`.
- **Positive control** (legitimate paths must keep working): from inside the `nginx` Pod,
  `curl` against the `frontend` Service returned the real SPA HTML (`<!doctype html>...
  CustomerWeb...`); `curl` against `nginx`'s own `/healthz` via its Service returned `ok`. Both
  exited `0`.
- **NetworkPolicy enforcement proven via real timing, not just declared intent**:
  - Test 1 — `nginx` → `postgres:5432` (must be **blocked**): `wget -T 3` from inside the
    `nginx` Pod hung until its own 3-second timeout and failed with `download timed out`,
    real elapsed time `3.455s`, exit code `1`. A silently-dropped SYN (Calico enforcing the
    default-deny) times out at the client's configured limit — this is the expected signature
    of a blocked connection, not an application-layer rejection.
  - Test 2 — `backend` → `postgres:5432` (must be **allowed**): `curl --max-time 3` from
    inside the `backend` Pod reached the server immediately and failed fast at the
    application layer (`curl: (52) Empty reply from server`, since `curl` does not speak the
    Postgres wire protocol) in real elapsed time `0.557s`, exit code `52`. Reaching and being
    rejected by the real Postgres process — not timing out — is the expected signature of an
    *allowed* connection to a server that doesn't understand HTTP.
  - The order-of-magnitude timing gap (`3.455s` timeout vs. `0.557s` fast-fail) is itself the
    evidence: a blocked path can only ever time out, an allowed path can only ever fail fast
    once it reaches a non-HTTP-speaking server.
- **Clean teardown**: `helm uninstall pizza-store -n pizza-store`, `kubectl delete namespace
  pizza-store`, `kind delete cluster --name pizza-store-validation` — confirmed via `kind get
  clusters` reporting `No kind clusters found.`, no lingering state.

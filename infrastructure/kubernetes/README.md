# Kubernetes

Helm chart (`helm/pizza-store/`) translating `infrastructure/swarm/docker-stack.yml` to
Kubernetes: Deployment/Service for `backend`/`frontend`/`nginx`, StatefulSet+PVC for
`postgres`/`mongodb`/`redis`/`rabbitmq`, a Secret for all credentials, an Ingress (assumes
ingress-nginx), HorizontalPodAutoscalers for `backend`/`frontend`, and NetworkPolicies
recreating the Compose/Swarm `edge-net`/`data-net` segmentation.

Validated end to end on a real local `kind` cluster — see
[`docs/deployment/kubernetes.md`](../../docs/deployment/kubernetes.md) for prerequisites,
install steps, the real translation/probe bugs caught and fixed during validation, and the
NetworkPolicy-enforcement proof.

> Status: Phase 8 (Issue #159) — done.

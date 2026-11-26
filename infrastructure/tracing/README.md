# Tracing

Distributed tracing: OpenTelemetry Collector and Jaeger.

## Local Compose services

Defined in `infrastructure/compose/docker-compose.yml` (Task #94), on `monitoring-net`:

- **OTel Collector** (`otel-collector-config.yml`) exposes the OTLP receiver on gRPC
  (`${OTEL_COLLECTOR_GRPC_PORT}:4317`) and HTTP (`${OTEL_COLLECTOR_HTTP_PORT}:4318`), forwards
  every span to Jaeger via OTLP/gRPC (`otlp/jaeger` exporter -> `jaeger:4317`), and also emits
  a `debug` exporter copy for local troubleshooting (`docker compose logs otel-collector`).
- **Jaeger** (`jaegertracing/all-in-one`) accepts OTLP natively — `COLLECTOR_OTLP_ENABLED=true`
  — and serves its UI at `${JAEGER_UI_PORT}:16686`.

```text
http://localhost:${JAEGER_UI_PORT:-16686}
```

**Why a separate collector when Jaeger accepts OTLP directly**: for a single-service local
stack it isn't strictly required — Jaeger's own OTLP endpoint would work standalone. It's kept
anyway because the master prompt and Epic #8 both name OpenTelemetry as the instrumentation
standard, and because Phase 6/7 application code should talk to a stable, vendor-neutral OTLP
collector endpoint rather than to Jaeger's endpoint directly: the collector can be repointed at
a different tracing backend later without touching any application configuration.

**In-memory storage only**: Jaeger here has no persistent volume, so traces are lost on
container restart. Documented as a known limitation of this baseline, not a decision to
revisit now — a real retention requirement doesn't exist until Phase 6/7 application traffic
does.

**No healthcheck on `otel-collector`**: `otel/opentelemetry-collector-contrib` is a
distroless, single-binary image — no shell, `wget`, `curl`, or even `ls` — verified
empirically, the same situation as `loki` in `infrastructure/logging/`. Jaeger (which does
have a shell and `wget`, and is health-checked on its UI's `/`) actually receiving the spans
this collector forwards is the real signal, proven below.

## Real synthetic-span validation

No backend/frontend exists yet to emit a real application trace (Phase 6/7's job), so this
Task's "real test, not a simulation" standard was applied to the one piece of the pipeline
that can be tested without an application: a single synthetic OTLP span, with a known random
trace/span ID, was POSTed as a minimal OTLP/HTTP JSON payload directly to
`http://localhost:${OTEL_COLLECTOR_HTTP_PORT}/v1/traces`, and that exact trace ID was then
fetched back from Jaeger's own query API
(`http://localhost:${JAEGER_UI_PORT}/api/traces/<trace-id>`) and confirmed present — proving
the full `otel-collector -> jaeger` OTLP forwarding path end to end, not just that both
containers report healthy.

## Known gap

Trace payloads may carry sensitive data once real application instrumentation lands in
Phase 6/7 (request parameters, user identifiers, etc. in span attributes). No such data
exists in this baseline — there is no application yet — but this is flagged here as a forward
note for whoever adds that instrumentation, not a decision this Task makes.

> Status: Phase 4 — OpenTelemetry Collector + Jaeger tracing skeleton implemented and
> validated with a real synthetic OTLP span sent through the collector and confirmed
> retrievable from Jaeger's query API. Unexercised by real application traffic until
> Phase 6/7 add OTLP instrumentation to the backend/frontend.

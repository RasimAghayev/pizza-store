# Security Policy

## Supported versions

The project is currently in Phase 0 (repository foundation); no released version exists yet.
Until the first stable version is announced, the `main` branch is the only supported line.

## Reporting a vulnerability

If you discover a security vulnerability, **do not open a public Issue**.

- Use GitHub Private Vulnerability Reporting ("Report a vulnerability" under the "Security"
  tab) once it's active.
- Alternatively, email rasimaqayev@gmail.com.

Include a description, reproduction steps, and the scope of impact in your report. We aim to
respond as quickly as possible (target: initial response within 7 business days).

## Scope

- Authentication/authorization issues, data leaks, injection, SSRF, secret exposure: critical.
- Dependency vulnerabilities are tracked via Dependabot/Renovate.
- Secrets must never be committed to the repository (push protection is active).

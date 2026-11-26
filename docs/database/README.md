# Database

Database Responsibility Matrix, PostgreSQL schema strategy, MongoDB collections, Redis key strategy, ERD.

- [Database Responsibility Matrix](responsibility-matrix.md) — every entity from master
  prompt §6/§11 mapped to PostgreSQL, MongoDB, or Redis.
- [Redis Caching and TTL Policy](redis-caching-and-ttl-policy.md) — key pattern, TTL, and
  invalidation trigger for every Redis-held entity.

> Status: Phase 1 — responsibility matrix and Redis TTL policy added; PostgreSQL schema,
> MongoDB collections, and ERD follow once Phase 6 implements the modules.

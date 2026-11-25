# ADR 0001: Modular Monolith + Event-Driven Architecture

## Status

Accepted

## Context

The Pizza Store Platform will manage all operations (customer, order, payment, courier,
inventory, loyalty, management) of a real restaurant chain. The project is starting from
scratch, and real load and domain boundaries haven't been proven by experience yet.

Two main options were considered:

1. A Microservices architecture from the start.
2. Modular Monolith + Event-Driven Architecture (EDA), with the option to split selected
   modules into microservices later.

## Decision

Modular Monolith + EDA is chosen.

- Clearly separated apps by domain (bounded context) within Django: identity, customers,
  restaurants, branches, menu, products, pricing, cart, orders, payments, kitchen, inventory,
  couriers, delivery, loyalty, notifications, reviews, analytics, audit.
- Direct dependencies between modules are minimized; communication favors domain events over
  RabbitMQ rather than synchronous calls (OrderCreated, PaymentCompleted, etc.).
- Clean Architecture, DDD, SOLID, Repository Pattern, Service Layer, and Dependency Injection
  are applied so that module boundaries are also protected at the code level.

## Reason

- A single deployment unit keeps operational complexity (multiple services, networking,
  distributed transactions) low in the first stage.
- Because bounded contexts are already clearly separated, a module can be extracted into its
  own microservice once real scaling need arises (e.g. if delivery tracking or notifications
  take on high load) — the monolith doesn't block this, it simply doesn't force it now.
- EDA via RabbitMQ, even within a monolith, prevents tight coupling from forming between
  modules and makes a future split easier.

## Consequences

- The Transactional Outbox Pattern is mandatory: if a PostgreSQL transaction succeeds but
  RabbitMQ is unreachable, the event must not be lost.
- Idempotent consumers are mandatory: if the same event arrives twice, the payment/order
  operation must not be executed twice.
- A move to microservices is only evaluated via a separate ADR once a real domain and scaling
  need is proven — no microservice is created artificially.

## Alternatives

- **Microservices from the start:** rejected — from day one, distributed system complexity
  (service discovery, distributed tracing, data consistency across services) would add
  operational cost without creating business value.
- **Classic monolith (without EDA, using direct function calls):** rejected — creates tight
  coupling between modules, makes a future split harder, and doesn't naturally support
  requirements like audit/retry/replay.

# Wallet

Owns a customer's monetary wallet balance and its append-only transaction ledger (Issue #199):
usable as a payment method at checkout alongside cash on delivery and online payment, topped
up through those same gateways, and ready to receive a refund credit from a future Task.

## Scope boundaries (deliberately out of this Task)

- **Loyalty points, cashback, reward tiers** -- Phase 13's ("Loyalty, Marketing &
  Management") scope, not this one's. This module's balance is plain money: top-up and
  spend, nothing else.
- **A real refund-triggering endpoint** -- `WalletGateway.refund()` exists and is unit
  tested, but nothing in this codebase calls it yet; Issue #200 (Refund/reconciliation) is
  its first real caller.
- **Multi-currency** -- same single implicit `DEFAULT_CURRENCY = "USD"` decision as
  `apps.payments.services.payment_service` (`services/wallet_service.py`), for the same
  reason: no multi-currency requirement exists anywhere else in this codebase.

## Ledger-only balance-mutation rule

`WalletAccount.balance` is a denormalized cache of `WalletTransaction`'s running sum. The
only two places that ever write it are `WalletService.credit()` and `WalletService.debit()`
(`services/wallet_service.py`), and both always write the matching `WalletTransaction` row in
the same `transaction.atomic()` block as the balance update -- there is no code path that
writes one without the other (Issue #199 Security Requirements). `debit()` additionally holds
a `select_for_update()` lock on the `WalletAccount` row for the lifetime of that transaction
and raises `InsufficientBalanceError` rather than ever letting the balance go negative; this
is what makes two concurrent debits against the same wallet serialize instead of racing (see
`tests/integration/test_wallet_concurrency.py`).

`reference_id` on `WalletTransaction` is left `None` by every writer in this Task. It exists
to eventually point at the row named by `reference_type` (e.g. an `Order`/`Payment` for
`order_payment`/`refund`), but no gateway call site in this Task has such an id available --
`WalletGateway.authorize()`/`refund()` only receive what Issue #198's `PaymentGateway`
interface carries (amount, currency, a payment method token, an idempotency key, and, since
this Task, `customer_id`), and a direct top-up has no row to point at either.
`reference_type` alone already categorizes each ledger entry; nothing in this Task's
Acceptance Criteria (ledger-equals-balance reconciliation, no overdraft under concurrency)
depends on `reference_id` being populated. Revisit if a later Task needs to join a ledger row
back to a specific `Order`/`Payment`.

## `WalletGateway` and the one-way dependency direction (ADR 0004)

`domain/wallet_gateway.py::WalletGateway` implements Issue #198's `PaymentGateway` interface:
`authorize()` performs the actual debit immediately (there is no separate hold/settle
distinction for an in-process ledger the way there is for a real PSP); `capture()` is then a
no-op that just reports the authorization as already settled, since
`PaymentService.capture_for_order()` always calls both in sequence; `refund()` credits the
wallet back.

Issue #199 asks for two things that look contradictory at first: "this Task edits
`apps.payments.domain.gateway_registry`" and "`apps.payments` never imports anything from
`apps.wallet`". Both are satisfied by Django's own `AppConfig.ready()` plugin-registration
idiom:

- `gateway_registry.py` gained a new public function, `register_gateway(payment_method,
  gateway)`, that mutates the registry dict -- `apps.payments` itself has no static import of
  `apps.wallet` anywhere.
- `apps/wallet/apps.py::WalletConfig.ready()` calls `register_gateway(PaymentMethod.WALLET,
  WalletGateway())` at Django startup, importing `apps.payments`'s registry and
  `WalletGateway` only inside the method body (not at module import time, since the app
  registry is not guaranteed fully populated until `ready()` runs).

This is the first `AppConfig.ready()` hook in this codebase; `PaymentMethod.WALLET` was added
to `apps.payments.domain.payment_method.PaymentMethod` with a comment pointing back here,
documenting that it is registered at runtime, never imported statically.

### Widening `PaymentGateway.authorize()`/`refund()` with `customer_id`

Issue #198's `PaymentGateway` interface carried no value identifying the customer -- it never
needed to, since neither `CashOnDeliveryGateway` nor `MockOnlineGateway` act on a specific
customer's own state. `WalletGateway` does: it must know whose `WalletAccount` to lock and
debit/credit. Rather than smuggle a customer id through the unrelated
`payment_method_token` field, `apps/payments/domain/gateway.py`'s `authorize()` and
`refund()` were widened to accept `customer_id: int`, and
`PaymentService.capture_for_order()` (`apps/payments/services/payment_service.py`) now passes
its own `customer_id` straight through. `CashOnDeliveryGateway`/`MockOnlineGateway` accept and
ignore the new parameter, the same way they already ignored `payment_method_token` where it
doesn't apply. See `apps/payments/README.md`'s "Gateway abstraction design" section for the
payments-side view of this same decision.

## Top-up funding (`services/topup_service.py::TopUpService`)

Topping up the wallet is itself funded through Issue #198's existing gateways: `TopUpService
.top_up()` calls `apps.payments.domain.gateway_registry.get_gateway(payment_method)` directly
(`cash_on_delivery` or `mock_online` -- never `wallet` itself, rejected by
`api/serializers.py::TopUpRequestSerializer`'s choice list), authorizes then captures the
top-up amount, and only credits the wallet once both succeed. A declined charge raises
`TopUpFailedError` before the ledger is ever touched.

This path never touches `apps.payments.models.Payment` or `PaymentService` -- a top-up has no
`Order` to attach a `Payment` row to, and Issue #199's own Technical Context is explicit that
this Task "does not duplicate Issue #198's `Payment` model or `PaymentService`", only reuses
its gateway abstraction. `apps.wallet` depends on `apps.payments`; `apps.payments` never
imports from `apps.wallet` (ADR 0004).

## Authorization

`IsAuthenticated` only -- the wallet resolved for any request is always this authenticated
user's own, via `ProfileService.get_profile(request.user.pk).pk`, never a client-supplied
customer or wallet id (Issue #199 Security Requirements; same pattern as
`apps.payments.api.views._customer_id_for`).

## `api/` endpoints

- `POST /api/v1/wallet/topup/` -- `amount`, `payment_method` (`cash_on_delivery` or
  `mock_online`), and (only for `mock_online`) `payment_method_token`; mandatory
  `Idempotency-Key` header, same reasoning as `apps.payments.api.views.PaymentCaptureView` --
  a duplicate top-up request must never double-charge or double-credit the wallet. `201` with
  the new `balance`/`currency`, or the first response, replayed, on a duplicate key. `400` for
  a missing header, `wallet` as the funding method, a mismatched `payment_method_token`
  requirement, or a declined charge.
- `GET /api/v1/wallet/` -- `balance`, `currency`, and the full `transactions` ledger history
  for this customer's wallet.

Paying for an order with the wallet uses the existing `POST /api/v1/payments/` endpoint
(`apps/payments/api/views.py::PaymentCaptureView`) with `payment_method: "wallet"` -- there is
no separate wallet-specific checkout endpoint; `WalletGateway` is just another registered
gateway from that view's perspective.

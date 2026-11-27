"""Pure order-lifecycle state machine (Issue #197) -- no Django import (ADR 0004), same
style as `apps/products/domain/pricing.py` / `apps/menu/domain/availability.py`. `OrderStatus`
is a Django-free `StrEnum` reused by `Order.status`'s `choices=` the same way
`apps.identity.domain.rbac.RoleCode` is reused by `RoleAssignment.role_code`.

`DRAFT`/`CART` (master prompt §11's lifecycle) is deliberately not a member of this enum: an
`Order` row is never created until checkout (Issue #196's `Cart` is that pre-order state), so
no `Order.status` value ever needs to represent it.

Two edges this Task's own choice settles, since the master prompt/Issue text names every
*node* but not every edge (documented here and in `backend/apps/orders/README.md`, same
"Task's own documented choice" pattern as Issue #196's branch-switch rule):

- `CANCELLED` is reachable from every active, non-terminal pre-`DELIVERED` status, not just
  `PENDING_PAYMENT` -- a pizza order can be aborted at any stage before it reaches the
  customer (kitchen incident, closed branch, courier failure), and this Task does not gate
  that on how far the order has already progressed.
- `PAYMENT_FAILED` can transition back to `PENDING_PAYMENT` (a client-initiated payment
  retry on the same order) in addition to `CANCELLED` (giving up).

`REFUND_PENDING` is reachable only from `CANCELLED` and `DELIVERED` -- not from any
mid-fulfillment status -- matching Issue #200's own explicit design ("for a full refund,
transitions the related Order to REFUND_PENDING... it was already in a terminal-ish state
such as CANCELLED or DELIVERED"): a refund reverses money already captured for an order that
has stopped moving forward, it is not itself how an in-flight order gets stopped.

Every edge from `ACCEPTED` onward through `DELIVERED` exists for Phase 12 (kitchen/delivery)
to drive via `OrderService.transition()` and is not reachable through any Phase 11 endpoint;
see `backend/apps/orders/README.md`.
"""

from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_FAILED = "payment_failed"
    CONFIRMED = "confirmed"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    BAKING = "baking"
    READY = "ready"
    COURIER_ASSIGNED = "courier_assigned"
    PICKED_UP = "picked_up"
    ON_THE_WAY = "on_the_way"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


class IllegalOrderTransitionError(Exception):
    def __init__(self, *, current: OrderStatus, target: OrderStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition an order from {current} to {target}.")


TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING_PAYMENT: frozenset(
        {OrderStatus.CONFIRMED, OrderStatus.PAYMENT_FAILED, OrderStatus.CANCELLED}
    ),
    OrderStatus.PAYMENT_FAILED: frozenset({OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.PREPARING, OrderStatus.CANCELLED}),
    OrderStatus.PREPARING: frozenset({OrderStatus.BAKING, OrderStatus.CANCELLED}),
    OrderStatus.BAKING: frozenset({OrderStatus.READY, OrderStatus.CANCELLED}),
    OrderStatus.READY: frozenset({OrderStatus.COURIER_ASSIGNED, OrderStatus.CANCELLED}),
    OrderStatus.COURIER_ASSIGNED: frozenset({OrderStatus.PICKED_UP, OrderStatus.CANCELLED}),
    OrderStatus.PICKED_UP: frozenset({OrderStatus.ON_THE_WAY, OrderStatus.CANCELLED}),
    OrderStatus.ON_THE_WAY: frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.REFUND_PENDING}),
    OrderStatus.CANCELLED: frozenset({OrderStatus.REFUND_PENDING}),
    OrderStatus.REFUND_PENDING: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.REFUNDED: frozenset(),
}


def next_status(*, current: OrderStatus, target: OrderStatus) -> OrderStatus:
    """Returns `target` on a legal transition, raises `IllegalOrderTransitionError`
    otherwise. Called by `OrderService.transition()` -- the sole writer of
    `OrderStatusAudit` rows (Issue #197) -- so every status change in this system is checked
    against this one table."""
    if target not in TRANSITIONS[current]:
        raise IllegalOrderTransitionError(current=current, target=target)
    return target

import pytest

from apps.orders.domain.state_machine import (
    TRANSITIONS,
    IllegalOrderTransitionError,
    OrderStatus,
    next_status,
)


def test_every_status_has_a_transition_table_entry():
    assert set(TRANSITIONS) == set(OrderStatus)


@pytest.mark.parametrize("current", list(OrderStatus))
@pytest.mark.parametrize("target", list(OrderStatus))
def test_every_status_pair_matches_the_transition_table(current, target):
    """Exhaustive sweep (Issue #197 Test Requirements) over every `OrderStatus x OrderStatus`
    pair -- a legal edge returns `target`, an illegal one (including every self-transition,
    none of which `TRANSITIONS` lists) raises."""
    if target in TRANSITIONS[current]:
        assert next_status(current=current, target=target) == target
    else:
        with pytest.raises(IllegalOrderTransitionError) as exc_info:
            next_status(current=current, target=target)
        assert exc_info.value.current == current
        assert exc_info.value.target == target


def test_cancelled_is_reachable_from_every_pre_delivered_non_terminal_status():
    """This Task's own documented choice -- see `state_machine.py`'s module docstring."""
    terminal_or_post_delivery = {
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
        OrderStatus.REFUND_PENDING,
        OrderStatus.REFUNDED,
    }
    for status in OrderStatus:
        if status in terminal_or_post_delivery:
            continue
        assert OrderStatus.CANCELLED in TRANSITIONS[status]


def test_payment_failed_can_retry_back_to_pending_payment():
    """This Task's own documented choice -- see `state_machine.py`'s module docstring."""
    assert OrderStatus.PENDING_PAYMENT in TRANSITIONS[OrderStatus.PAYMENT_FAILED]


def test_refund_pending_is_reachable_only_from_cancelled_and_delivered():
    """Matches Issue #200's own explicit design -- see `state_machine.py`'s module
    docstring."""
    sources = {
        status for status, targets in TRANSITIONS.items() if OrderStatus.REFUND_PENDING in targets
    }
    assert sources == {OrderStatus.CANCELLED, OrderStatus.DELIVERED}


def test_refunded_is_terminal():
    assert TRANSITIONS[OrderStatus.REFUNDED] == frozenset()


def test_kitchen_and_delivery_edges_exist_for_phase_12_even_though_unreachable_this_task():
    assert TRANSITIONS[OrderStatus.CONFIRMED] >= {OrderStatus.ACCEPTED}
    assert TRANSITIONS[OrderStatus.ACCEPTED] >= {OrderStatus.PREPARING}
    assert TRANSITIONS[OrderStatus.PREPARING] >= {OrderStatus.BAKING}
    assert TRANSITIONS[OrderStatus.BAKING] >= {OrderStatus.READY}
    assert TRANSITIONS[OrderStatus.READY] >= {OrderStatus.COURIER_ASSIGNED}
    assert TRANSITIONS[OrderStatus.COURIER_ASSIGNED] >= {OrderStatus.PICKED_UP}
    assert TRANSITIONS[OrderStatus.PICKED_UP] >= {OrderStatus.ON_THE_WAY}
    assert TRANSITIONS[OrderStatus.ON_THE_WAY] >= {OrderStatus.DELIVERED}

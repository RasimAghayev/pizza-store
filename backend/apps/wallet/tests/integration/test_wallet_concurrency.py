import threading
from decimal import Decimal

import pytest
from django.db import connection

from apps.wallet.domain.reference_type import WalletReferenceType
from apps.wallet.services.wallet_service import InsufficientBalanceError, WalletService

CUSTOMER_ID = 9191


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_debits_against_the_same_wallet_can_never_together_overdraw_it():
    """Issue #199 Acceptance Criteria: a debit can never take the balance negative, even under
    concurrent requests. Same real-threads-plus-barrier pattern as
    shared/tests/integration/test_idempotency_service.py::
    test_concurrent_requests_for_the_same_key_never_return_two_different_responses. Both
    threads race to debit 6.00 from a 10.00 balance -- only one can possibly succeed;
    `select_for_update()` must serialize the two so the loser re-reads the already-decremented
    balance and raises, rather than the balance ever going to -2.00."""
    WalletService().credit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("10.00"),
        reference_type=WalletReferenceType.TOPUP,
        reference_id=None,
    )
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    errors: list[Exception] = []

    def worker():
        try:
            barrier.wait(timeout=5)  # widen the race window so both threads overlap
            WalletService().debit(
                customer_id=CUSTOMER_ID,
                amount=Decimal("6.00"),
                reference_type=WalletReferenceType.ORDER_PAYMENT,
                reference_id=None,
            )
            outcomes.append("succeeded")
        except InsufficientBalanceError:
            outcomes.append("rejected")
        except Exception as exc:  # noqa: BLE001 -- captured for the main thread to assert on
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert sorted(outcomes) == ["rejected", "succeeded"]

    wallet = WalletService().get_or_create_wallet(customer_id=CUSTOMER_ID)
    assert wallet.balance == Decimal("4.00")

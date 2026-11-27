from decimal import Decimal

import pytest

from apps.wallet.domain.reference_type import WalletReferenceType
from apps.wallet.domain.transaction_type import WalletTransactionType
from apps.wallet.models.wallet_transaction import WalletTransaction
from apps.wallet.services.wallet_service import InsufficientBalanceError, WalletService

CUSTOMER_ID = 4242


@pytest.mark.django_db
def test_credit_increases_balance_by_the_exact_decimal_amount():
    wallet = WalletService().credit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("10.00"),
        reference_type=WalletReferenceType.TOPUP,
        reference_id=None,
    )

    assert wallet.balance == Decimal("10.00")


@pytest.mark.django_db
def test_credit_then_debit_leaves_the_exact_remaining_decimal_balance():
    service = WalletService()
    service.credit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("10.00"),
        reference_type=WalletReferenceType.TOPUP,
        reference_id=None,
    )

    wallet = service.debit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("3.33"),
        reference_type=WalletReferenceType.ORDER_PAYMENT,
        reference_id=None,
    )

    assert wallet.balance == Decimal("6.67")


@pytest.mark.django_db
def test_debit_beyond_the_current_balance_raises_and_leaves_balance_unchanged():
    service = WalletService()
    service.credit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("5.00"),
        reference_type=WalletReferenceType.TOPUP,
        reference_id=None,
    )

    with pytest.raises(InsufficientBalanceError):
        service.debit(
            customer_id=CUSTOMER_ID,
            amount=Decimal("5.01"),
            reference_type=WalletReferenceType.ORDER_PAYMENT,
            reference_id=None,
        )

    wallet = service.get_or_create_wallet(customer_id=CUSTOMER_ID)
    assert wallet.balance == Decimal("5.00")


@pytest.mark.django_db
def test_debit_against_a_wallet_that_was_never_topped_up_raises():
    with pytest.raises(InsufficientBalanceError):
        WalletService().debit(
            customer_id=CUSTOMER_ID,
            amount=Decimal("1.00"),
            reference_type=WalletReferenceType.ORDER_PAYMENT,
            reference_id=None,
        )


@pytest.mark.django_db
def test_a_failed_debit_writes_no_ledger_row_at_all():
    service = WalletService()
    wallet = service.credit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("5.00"),
        reference_type=WalletReferenceType.TOPUP,
        reference_id=None,
    )

    with pytest.raises(InsufficientBalanceError):
        service.debit(
            customer_id=CUSTOMER_ID,
            amount=Decimal("5.01"),
            reference_type=WalletReferenceType.ORDER_PAYMENT,
            reference_id=None,
        )

    assert WalletTransaction.objects.filter(wallet_id=wallet.pk).count() == 1


@pytest.mark.django_db
def test_every_credit_and_debit_writes_exactly_one_ledger_row_of_the_matching_type():
    service = WalletService()
    wallet = service.credit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("10.00"),
        reference_type=WalletReferenceType.TOPUP,
        reference_id=None,
    )
    service.debit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("4.00"),
        reference_type=WalletReferenceType.ORDER_PAYMENT,
        reference_id=None,
    )

    rows = list(WalletTransaction.objects.filter(wallet_id=wallet.pk).order_by("created_at"))
    assert [row.type for row in rows] == [WalletTransactionType.CREDIT, WalletTransactionType.DEBIT]
    assert [row.amount for row in rows] == [Decimal("10.00"), Decimal("4.00")]


@pytest.mark.django_db
def test_balance_always_equals_the_ledgers_running_sum():
    """Issue #199 Acceptance Criteria: `balance` always equals the ledger's running sum."""
    service = WalletService()
    wallet = service.credit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("20.00"),
        reference_type=WalletReferenceType.TOPUP,
        reference_id=None,
    )
    service.debit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("7.50"),
        reference_type=WalletReferenceType.ORDER_PAYMENT,
        reference_id=None,
    )
    service.credit(
        customer_id=CUSTOMER_ID,
        amount=Decimal("2.25"),
        reference_type=WalletReferenceType.REFUND,
        reference_id=None,
    )

    ledger_sum = Decimal("0.00")
    for row in WalletTransaction.objects.filter(wallet_id=wallet.pk):
        ledger_sum += row.amount if row.type == WalletTransactionType.CREDIT else -row.amount

    wallet.refresh_from_db()
    assert wallet.balance == ledger_sum == Decimal("14.75")

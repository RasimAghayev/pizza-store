from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# calls apps.customers.services.profile_service.ProfileService.get_profile() -- see
# backend/apps/customers/README.md. The wallet resolved for any request is always this
# authenticated user's own customer_id, never a client-supplied id (Issue #199 Security
# Requirements). Same pattern as apps.payments.api.views._customer_id_for.
from apps.customers.services.profile_service import CustomerNotFoundError as ProfileNotFoundError
from apps.customers.services.profile_service import ProfileService
from apps.payments.domain.gateway_registry import UnknownPaymentMethodError
from apps.wallet.api.serializers import (
    TopUpRequestSerializer,
    TopUpResponseSerializer,
    WalletBalanceResponseSerializer,
)
from apps.wallet.services.topup_service import TopUpFailedError, TopUpService
from apps.wallet.services.wallet_service import WalletService
from shared.idempotency.drf import IdempotentActionMixin


def _customer_id_for(request) -> int:
    try:
        return ProfileService().get_profile(request.user.pk).pk
    except ProfileNotFoundError as exc:
        raise exceptions.NotFound("Customer profile not found.") from exc


class WalletTopUpView(IdempotentActionMixin, APIView):
    """calls TopUpService.top_up() -- see apps/wallet/services/topup_service.py. The
    `Idempotency-Key` header is mandatory, same reasoning as
    apps.payments.api.views.PaymentCaptureView: a duplicate top-up request must never
    double-charge or double-credit the wallet."""

    permission_classes = [IsAuthenticated]

    def post(self, request, version):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            raise exceptions.ValidationError(
                {"Idempotency-Key": "This header is required for a wallet top-up."}
            )

        customer_id = _customer_id_for(request)
        serializer = TopUpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data["amount"]
        payment_method = serializer.validated_data["payment_method"]
        payment_method_token = serializer.validated_data.get("payment_method_token")

        def handler() -> tuple[int, object]:
            try:
                wallet = TopUpService().top_up(
                    customer_id=customer_id,
                    amount=amount,
                    payment_method=payment_method,
                    payment_method_token=payment_method_token,
                    idempotency_key=idempotency_key,
                )
            except TopUpFailedError as exc:
                raise exceptions.ValidationError(
                    {"payment_method": exc.failure_reason or "top_up_failed"}
                ) from exc
            except UnknownPaymentMethodError as exc:
                raise exceptions.ValidationError("Unknown payment method.") from exc
            body = TopUpResponseSerializer(
                {"balance": wallet.balance, "currency": wallet.currency}
            ).data
            return 201, body

        return self.perform_idempotent(scope="wallet.topup", handler=handler)


class WalletBalanceView(APIView):
    """calls WalletService.get_or_create_wallet()/list_transactions() -- see
    apps/wallet/services/wallet_service.py."""

    permission_classes = [IsAuthenticated]

    def get(self, request, version):
        customer_id = _customer_id_for(request)
        wallets = WalletService()
        wallet = wallets.get_or_create_wallet(customer_id=customer_id)
        transactions = wallets.list_transactions(wallet.pk)
        body = WalletBalanceResponseSerializer(
            {"balance": wallet.balance, "currency": wallet.currency, "transactions": transactions}
        ).data
        return Response(body)

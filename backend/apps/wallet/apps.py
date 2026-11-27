from django.apps import AppConfig


class WalletConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.wallet"
    label = "wallet"

    def ready(self) -> None:
        # calls apps.payments.domain.gateway_registry.register_gateway() -- see
        # backend/apps/wallet/domain/wallet_gateway.py and
        # backend/apps/payments/domain/gateway_registry.py. Imported here, not at module level,
        # per Django's own AppConfig.ready() convention: the app registry is not fully
        # populated until ready() runs, so importing apps.payments/apps.wallet models at import
        # time of this module could fail depending on INSTALLED_APPS order.
        from apps.payments.domain.gateway_registry import register_gateway
        from apps.payments.domain.payment_method import PaymentMethod
        from apps.wallet.domain.wallet_gateway import WalletGateway

        register_gateway(PaymentMethod.WALLET, WalletGateway())

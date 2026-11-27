from django.urls import path

from apps.wallet.api.views import WalletBalanceView, WalletTopUpView

urlpatterns = [
    path("", WalletBalanceView.as_view(), name="wallet-balance"),
    path("topup/", WalletTopUpView.as_view(), name="wallet-topup"),
]

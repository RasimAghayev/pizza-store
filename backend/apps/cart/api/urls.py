from django.urls import path

from apps.cart.api.views import CartItemDetailView, CartView

urlpatterns = [
    path("", CartView.as_view(), name="cart"),
    path("items/<int:pk>/", CartItemDetailView.as_view(), name="cart-item-detail"),
]

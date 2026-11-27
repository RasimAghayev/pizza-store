from django.urls import path

from apps.products.api.views import (
    AllergenDetailView,
    AllergenListCreateView,
    OptionGroupChoicesView,
    PriceQuoteView,
    ProductAllergensView,
    ProductDetailView,
    ProductListCreateView,
    ProductOptionGroupsView,
    ProductToppingDetailView,
    ProductToppingsView,
    ToppingDetailView,
    ToppingListCreateView,
)

urlpatterns = [
    path("toppings/", ToppingListCreateView.as_view(), name="topping-list-create"),
    path("toppings/<int:pk>/", ToppingDetailView.as_view(), name="topping-detail"),
    path("allergens/", AllergenListCreateView.as_view(), name="allergen-list-create"),
    path("allergens/<int:pk>/", AllergenDetailView.as_view(), name="allergen-detail"),
    path("", ProductListCreateView.as_view(), name="product-list-create"),
    path("<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path(
        "<int:pk>/option-groups/",
        ProductOptionGroupsView.as_view(),
        name="product-option-groups",
    ),
    path(
        "<int:pk>/option-groups/<int:group_id>/choices/",
        OptionGroupChoicesView.as_view(),
        name="option-group-choices",
    ),
    path("<int:pk>/toppings/", ProductToppingsView.as_view(), name="product-toppings"),
    path(
        "<int:pk>/toppings/<int:topping_id>/",
        ProductToppingDetailView.as_view(),
        name="product-topping-detail",
    ),
    path("<int:pk>/allergens/", ProductAllergensView.as_view(), name="product-allergens"),
    path("<int:pk>/price-quote/", PriceQuoteView.as_view(), name="product-price-quote"),
]

# called by Nginx/a future load balancer's health probe -- see backend/health/views.py
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# calls GET /api/v1/branches/<branch_id>/menu/ -- see
# backend/apps/menu/api/views.py::BranchMenuView (Issue #182)
from apps.menu.api.views import BranchMenuView

# calls GET /api/v1/ping/ -- see backend/shared/api/views.py::PingView
from shared.api.views import PingView

urlpatterns = [
    path("health/", include("health.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # Every module's api/urls.py will be mounted the same way, under
    # api/<version>/<module>/... -- see docs/api/conventions.md.
    path("api/<str:version>/ping/", PingView.as_view(), name="ping"),
    # calls POST /api/v1/auth/{login,refresh,logout} -- see
    # backend/apps/identity/api/views.py (Issue #129)
    path("api/<str:version>/auth/", include("apps.identity.api.urls")),
    # calls POST /api/v1/customers/register/ -- see
    # backend/apps/customers/api/views.py (Issue #176)
    path("api/<str:version>/customers/", include("apps.customers.api.urls")),
    # calls GET/POST/PATCH/DELETE /api/v1/restaurants/{,<id>/,organizations/...} -- see
    # backend/apps/restaurants/api/views.py (Issue #180)
    path("api/<str:version>/restaurants/", include("apps.restaurants.api.urls")),
    # calls GET/POST/PATCH/DELETE /api/v1/branches/{,<id>/,<id>/hours/,<id>/closures/} -- see
    # backend/apps/branches/api/views.py (Issue #180)
    path("api/<str:version>/branches/", include("apps.branches.api.urls")),
    # calls GET/POST/PATCH/DELETE /api/v1/products/{,<id>/,toppings/...,allergens/...,
    # <id>/price-quote/} -- see backend/apps/products/api/views.py (Issue #181)
    path("api/<str:version>/products/", include("apps.products.api.urls")),
    # Mounted under the branches/ prefix but owned by apps.menu, not apps.branches.api.urls
    # (ADR 0004 dependency direction: menu depends on branches, never the reverse) -- see
    # BranchMenuView above (Issue #182).
    path(
        "api/<str:version>/branches/<int:branch_id>/menu/",
        BranchMenuView.as_view(),
        name="branch-menu",
    ),
    # calls GET/POST/PATCH/DELETE /api/v1/menu/{categories,items}/... -- see
    # backend/apps/menu/api/views.py (Issue #182)
    path("api/<str:version>/menu/", include("apps.menu.api.urls")),
    # calls GET/POST/DELETE /api/v1/cart/ and PATCH/DELETE /api/v1/cart/items/<id>/ -- see
    # backend/apps/cart/api/views.py (Issue #196)
    path("api/<str:version>/cart/", include("apps.cart.api.urls")),
]

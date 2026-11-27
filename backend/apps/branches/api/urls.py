from django.urls import path

from apps.branches.api.views import (
    BranchClosureDetailView,
    BranchClosuresView,
    BranchDetailView,
    BranchHoursView,
    BranchIsOpenView,
    BranchListCreateView,
    BranchNearbyView,
)

urlpatterns = [
    path("nearby/", BranchNearbyView.as_view(), name="branch-nearby"),
    path("", BranchListCreateView.as_view(), name="branch-list-create"),
    path("<int:pk>/", BranchDetailView.as_view(), name="branch-detail"),
    path("<int:pk>/is-open/", BranchIsOpenView.as_view(), name="branch-is-open"),
    path("<int:pk>/hours/", BranchHoursView.as_view(), name="branch-hours"),
    path("<int:pk>/closures/", BranchClosuresView.as_view(), name="branch-closures"),
    path(
        "<int:pk>/closures/<int:closure_id>/",
        BranchClosureDetailView.as_view(),
        name="branch-closure-detail",
    ),
]

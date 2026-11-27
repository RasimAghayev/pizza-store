from django.conf import settings
from django.db import models

from apps.identity.domain.rbac import RoleCode


class RoleAssignment(models.Model):
    """One row per (user, role, scope) -- ADR 0006. `organization_id`/`branch_id` are plain
    fields, not Django ForeignKeys: `restaurants`/`branches` don't exist yet, and ADR 0004
    forbids `identity` importing their models even once they do. Scope is always re-derived
    from the resource being acted on at permission-check time (see
    `shared/permissions/base.py::TwoStepPermission`), never trusted from these columns alone
    for anything beyond "which scopes does this user hold.\""""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_assignments"
    )
    role_code = models.CharField(max_length=32, choices=[(code, code.value) for code in RoleCode])
    organization_id = models.PositiveBigIntegerField(null=True, blank=True)
    branch_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "identity"
        constraints = [
            # nulls_distinct=False (Postgres 16's NULLS NOT DISTINCT, Django 5+) -- a plain
            # UniqueConstraint would never actually block a duplicate here: every branch-scoped
            # role has organization_id always NULL (and vice versa for org-scoped roles), and
            # standard SQL treats NULL <> NULL, so two identical rows would both satisfy a
            # plain unique index.
            models.UniqueConstraint(
                fields=["user", "role_code", "organization_id", "branch_id"],
                name="unique_role_assignment_scope",
                nulls_distinct=False,
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.role_code}"

from django.core.exceptions import ImproperlyConfigured
from rest_framework.permissions import BasePermission


class TwoStepPermission(BasePermission):
    """ADR 0006's two-step authorization check, generic over whatever module uses it (ADR
    0004 -- this file imports no `apps.*` module). A concrete view sets a `required_permission`
    class attribute (e.g. `"branches.edit"`) and, for any view that calls
    `check_object_permissions` (retrieve/update/delete, not list/create), implements
    `scope_organization_id(obj)` / `scope_branch_id(obj)` returning that resource's own scope
    -- never a client-supplied value.

    Step 1 (`has_permission`): does any role the request's user holds, in any scope, grant
    `required_permission`. Delegates to `request.user.has_rbac_permission(permission)` -- a
    duck-typed contract on `settings.AUTH_USER_MODEL` (currently `identity.User`,
    `apps/identity/models/user.py`), not a direct import of that app.

    Step 2 (`has_object_permission`): re-checks step 1, then re-derives every role assignment
    that actually grants the permission (`request.user.role_assignments_granting(permission)`)
    and accepts if any one of them scopes to this exact resource -- an org-scoped assignment
    with no `branch_id` matches any branch under that org; a branch-scoped assignment matches
    only that branch; an assignment with neither set (e.g. Super Admin) matches anything.
    Re-derived fresh on every request, not read from the JWT's own `org_id`/`branch_id`
    claims, so a user holding the permission at multiple branches is checked against all of
    them (see `apps/identity/services/session_service.py::_claims_for`)."""

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return user.has_rbac_permission(self._required_permission(view))

    def has_object_permission(self, request, view, obj) -> bool:
        if not self.has_permission(request, view):
            return False

        permission = self._required_permission(view)
        user = request.user
        granting = user.role_assignments_granting(permission)
        if not granting:
            return False

        if not hasattr(view, "scope_organization_id") or not hasattr(view, "scope_branch_id"):
            raise ImproperlyConfigured(
                f"{view.__class__.__name__} uses TwoStepPermission but does not implement "
                "scope_organization_id(obj)/scope_branch_id(obj) -- failing closed rather "
                "than silently allowing an unscoped object check."
            )
        resource_org_id = view.scope_organization_id(obj)
        resource_branch_id = view.scope_branch_id(obj)

        for assignment in granting:
            if assignment.organization_id is None and assignment.branch_id is None:
                return True  # unscoped grant (e.g. Super Admin)
            if assignment.branch_id is not None and assignment.branch_id == resource_branch_id:
                return True
            if (
                assignment.branch_id is None
                and assignment.organization_id is not None
                and assignment.organization_id == resource_org_id
            ):
                return True
        return False

    @staticmethod
    def _required_permission(view) -> str:
        permission = getattr(view, "required_permission", None)
        if not permission:
            raise ImproperlyConfigured(
                f"{view.__class__.__name__} uses TwoStepPermission but does not set a "
                "required_permission class attribute."
            )
        return permission

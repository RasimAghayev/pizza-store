from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("User must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        app_label = "identity"

    def __str__(self) -> str:
        return self.email

    def has_rbac_permission(self, permission: str) -> bool:
        """Duck-typed contract `shared/permissions/base.py::TwoStepPermission` calls on
        whatever `settings.AUTH_USER_MODEL` is, without importing this app (ADR 0004) --
        step 1 of ADR 0006's two-step check: does any role this user holds grant `permission`,
        in any scope."""
        from apps.identity.domain.rbac import permissions_for

        role_codes = self.role_assignments.values_list("role_code", flat=True)
        return permission in permissions_for(list(role_codes))

    def role_assignments_granting(self, permission: str) -> list:
        """Step 2's input: every role assignment (with its own organization_id/branch_id) that
        grants `permission` -- re-derived fresh on every call, deliberately not read from the
        JWT claims, so a user holding the same permission at multiple branches is checked
        against all of them, not a single collapsed scope (see
        apps/identity/services/session_service.py::_claims_for)."""
        from apps.identity.domain.rbac import permissions_for

        return [
            assignment
            for assignment in self.role_assignments.all()
            if permission in permissions_for([assignment.role_code])
        ]

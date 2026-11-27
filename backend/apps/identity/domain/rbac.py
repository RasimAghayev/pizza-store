from enum import StrEnum


class RoleCode(StrEnum):
    """Every role from master prompt §11 (ADR 0006). Customer-facing roles are a progressive
    account state, not an assignable staff role; staff roles carry an organization/branch
    scope on their `RoleAssignment` row, never on the role definition itself."""

    # Customer-facing (progressive account state)
    CUSTOMER = "customer"
    VERIFIED_CUSTOMER = "verified_customer"
    LOYALTY_MEMBER = "loyalty_member"

    # Staff -- organization-scoped (branch_id null on the assignment)
    SUPER_ADMIN = "super_admin"
    ORGANIZATION_OWNER = "organization_owner"
    ACCOUNTANT = "accountant"
    MARKETING_MANAGER = "marketing_manager"

    # Staff -- branch-scoped
    RESTAURANT_MANAGER = "restaurant_manager"
    BRANCH_MANAGER = "branch_manager"
    CASHIER = "cashier"
    KITCHEN_MANAGER = "kitchen_manager"
    KITCHEN_STAFF = "kitchen_staff"
    DELIVERY_MANAGER = "delivery_manager"
    COURIER = "courier"
    INVENTORY_MANAGER = "inventory_manager"
    CUSTOMER_SUPPORT = "customer_support"


# "Guest" (master prompt §11) is the absence of any RoleAssignment row -- it is never stored.
_NO_SCOPE_CUSTOMER_FACING = frozenset(
    {RoleCode.CUSTOMER, RoleCode.VERIFIED_CUSTOMER, RoleCode.LOYALTY_MEMBER}
)

# Staff roles carrying organization-level scope (branch_id null on the assignment).
ORGANIZATION_SCOPED_ROLES = frozenset(
    {RoleCode.ORGANIZATION_OWNER, RoleCode.ACCOUNTANT, RoleCode.MARKETING_MANAGER}
)

# Staff roles carrying branch-level scope.
BRANCH_SCOPED_ROLES = frozenset(
    {
        RoleCode.RESTAURANT_MANAGER,
        RoleCode.BRANCH_MANAGER,
        RoleCode.CASHIER,
        RoleCode.KITCHEN_MANAGER,
        RoleCode.KITCHEN_STAFF,
        RoleCode.DELIVERY_MANAGER,
        RoleCode.COURIER,
        RoleCode.INVENTORY_MANAGER,
        RoleCode.CUSTOMER_SUPPORT,
    }
)

# Static role -> permission mapping (ADR 0006: "seeded... rather than editable at runtime" --
# no database-backed Role/Permission table exists). A permission string is "<module>.<action>".
# Only modules that exist as of this Task (identity itself) have real permissions below; later
# Phase 10 Tasks (restaurants, branches, products, menu) append their own module's permissions
# to the relevant roles' sets when those modules are built, rather than this file speculating
# about permissions for modules that don't exist yet.
ROLE_PERMISSIONS: dict[RoleCode, frozenset[str]] = {
    RoleCode.CUSTOMER: frozenset(),
    RoleCode.VERIFIED_CUSTOMER: frozenset(),
    RoleCode.LOYALTY_MEMBER: frozenset(),
    RoleCode.SUPER_ADMIN: frozenset({"identity.manage_roles"}),
    RoleCode.ORGANIZATION_OWNER: frozenset({"identity.manage_roles"}),
    RoleCode.ACCOUNTANT: frozenset(),
    RoleCode.MARKETING_MANAGER: frozenset(),
    RoleCode.RESTAURANT_MANAGER: frozenset(),
    RoleCode.BRANCH_MANAGER: frozenset(),
    RoleCode.CASHIER: frozenset(),
    RoleCode.KITCHEN_MANAGER: frozenset(),
    RoleCode.KITCHEN_STAFF: frozenset(),
    RoleCode.DELIVERY_MANAGER: frozenset(),
    RoleCode.COURIER: frozenset(),
    RoleCode.INVENTORY_MANAGER: frozenset(),
    RoleCode.CUSTOMER_SUPPORT: frozenset(),
}


def is_branch_scoped(role_code: RoleCode) -> bool:
    return role_code in BRANCH_SCOPED_ROLES


def is_organization_scoped(role_code: RoleCode) -> bool:
    return role_code in ORGANIZATION_SCOPED_ROLES


def permissions_for(role_codes: list[RoleCode]) -> frozenset[str]:
    permissions: set[str] = set()
    for code in role_codes:
        permissions |= ROLE_PERMISSIONS.get(code, frozenset())
    return frozenset(permissions)

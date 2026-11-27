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
#
# restaurants.*/branches.* (Issue #180): "view" governs read access to the staff-only
# Organization resource and to Restaurant/Branch when accessed through the authenticated
# (not the public, AllowAny) path; "edit" governs create/update/delete, always re-scoped by
# TwoStepPermission's step 2. Granted per real-world responsibility, not uniformly: an
# org-scoped holder (ORGANIZATION_OWNER) can open new restaurants/branches under their own
# org; a branch-scoped holder (RESTAURANT_MANAGER/BRANCH_MANAGER, per the existing
# BRANCH_SCOPED_ROLES grouping above) can edit their own branch's operational fields but
# can't create a new one -- TwoStepPermission's scope check on an unsaved instance naturally
# denies branch-scoped creation attempts (no branch id yet to match), so this isn't enforced
# by a separate rule. Every other branch-scoped staff role gets read-only branches.view -- they
# need a branch's hours/capacity/location for their own work but don't manage it.
#
# products.* (Issue #181): Product is org-scoped, never branch-scoped (menu availability per
# branch is Issue #182's concern), so "products.edit" is only granted to the two org-scoped
# roles that can ever satisfy TwoStepPermission's object-level check against a Product's
# `organization_id` -- a purely branch-scoped assignment's `branch_id` can never match a
# Product's `scope_branch_id()` (always None, see apps/products/api/views.py's
# `_ScopesToOwningOrganization`), so granting branch-scoped roles "products.edit" would be a
# permission that structurally can never pass step 2. Every staff role instead gets
# "products.view" alongside its existing branches.view -- cashiers ring up menu items,
# kitchen staff build them, inventory managers track their toppings' sku_reference, etc.,
# the same breadth already established for branches.view.
ROLE_PERMISSIONS: dict[RoleCode, frozenset[str]] = {
    RoleCode.CUSTOMER: frozenset(),
    RoleCode.VERIFIED_CUSTOMER: frozenset(),
    RoleCode.LOYALTY_MEMBER: frozenset(),
    RoleCode.SUPER_ADMIN: frozenset(
        {
            "identity.manage_roles",
            "restaurants.view",
            "restaurants.edit",
            "branches.view",
            "branches.edit",
            "products.view",
            "products.edit",
        }
    ),
    RoleCode.ORGANIZATION_OWNER: frozenset(
        {
            "identity.manage_roles",
            "restaurants.view",
            "restaurants.edit",
            "branches.view",
            "branches.edit",
            "products.view",
            "products.edit",
        }
    ),
    RoleCode.ACCOUNTANT: frozenset({"restaurants.view", "branches.view", "products.view"}),
    RoleCode.MARKETING_MANAGER: frozenset({"restaurants.view", "branches.view", "products.view"}),
    RoleCode.RESTAURANT_MANAGER: frozenset(
        {"restaurants.view", "branches.view", "branches.edit", "products.view"}
    ),
    RoleCode.BRANCH_MANAGER: frozenset(
        {"restaurants.view", "branches.view", "branches.edit", "products.view"}
    ),
    RoleCode.CASHIER: frozenset({"branches.view", "products.view"}),
    RoleCode.KITCHEN_MANAGER: frozenset({"branches.view", "products.view"}),
    RoleCode.KITCHEN_STAFF: frozenset({"branches.view", "products.view"}),
    RoleCode.DELIVERY_MANAGER: frozenset({"branches.view", "products.view"}),
    RoleCode.COURIER: frozenset({"branches.view", "products.view"}),
    RoleCode.INVENTORY_MANAGER: frozenset({"branches.view", "products.view"}),
    RoleCode.CUSTOMER_SUPPORT: frozenset({"branches.view", "products.view"}),
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

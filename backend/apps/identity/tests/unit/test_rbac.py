from apps.identity.domain.rbac import (
    ROLE_PERMISSIONS,
    RoleCode,
    is_branch_scoped,
    is_organization_scoped,
    permissions_for,
)

_CUSTOMER_FACING = {RoleCode.CUSTOMER, RoleCode.VERIFIED_CUSTOMER, RoleCode.LOYALTY_MEMBER}


def test_every_role_code_has_a_mapping_entry():
    assert set(ROLE_PERMISSIONS.keys()) == set(RoleCode)


def test_every_staff_role_is_either_branch_or_organization_scoped():
    for code in RoleCode:
        if code in _CUSTOMER_FACING or code is RoleCode.SUPER_ADMIN:
            continue
        assert is_branch_scoped(code) or is_organization_scoped(code), code
        assert not (is_branch_scoped(code) and is_organization_scoped(code)), code


def test_super_admin_and_customer_facing_roles_carry_no_scope():
    for code in (RoleCode.SUPER_ADMIN, *_CUSTOMER_FACING):
        assert not is_branch_scoped(code)
        assert not is_organization_scoped(code)


def test_permissions_for_unions_across_multiple_roles():
    permissions = permissions_for([RoleCode.SUPER_ADMIN, RoleCode.ORGANIZATION_OWNER])

    assert permissions == {"identity.manage_roles"}


def test_permissions_for_empty_role_list_is_empty():
    assert permissions_for([]) == frozenset()


def test_permissions_for_customer_facing_role_is_empty():
    assert permissions_for([RoleCode.CUSTOMER]) == frozenset()

from apps.cart.domain.branch_policy import can_add_to_branch


def test_allows_the_first_ever_item_with_no_existing_cart():
    assert can_add_to_branch(
        existing_cart_branch_id=None, existing_cart_has_items=False, requested_branch_id=1
    )


def test_allows_adding_to_the_same_branch_as_the_existing_non_empty_cart():
    assert can_add_to_branch(
        existing_cart_branch_id=5, existing_cart_has_items=True, requested_branch_id=5
    )


def test_rejects_a_different_branch_while_the_existing_cart_has_items():
    assert not can_add_to_branch(
        existing_cart_branch_id=5, existing_cart_has_items=True, requested_branch_id=9
    )


def test_allows_a_different_branch_when_the_existing_cart_for_another_branch_is_empty():
    assert can_add_to_branch(
        existing_cart_branch_id=5, existing_cart_has_items=False, requested_branch_id=9
    )

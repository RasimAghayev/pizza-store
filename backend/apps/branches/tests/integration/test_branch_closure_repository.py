from datetime import datetime, timezone

import pytest

from apps.branches.repositories.branch_closure_repository import BranchClosureRepository
from apps.branches.tests.factories import BranchFactory


@pytest.mark.django_db
def test_create_persists_a_closure():
    branch = BranchFactory()

    closure = BranchClosureRepository().create(
        branch_id=branch.pk,
        starts_at=datetime(2026, 12, 25, tzinfo=timezone.utc),
        ends_at=datetime(2026, 12, 26, tzinfo=timezone.utc),
        reason="Christmas",
    )

    assert closure.pk is not None
    assert closure.reason == "Christmas"


@pytest.mark.django_db
def test_for_branch_returns_only_that_branchs_closures():
    branch_a, branch_b = BranchFactory(), BranchFactory()
    repository = BranchClosureRepository()
    wanted = repository.create(
        branch_id=branch_a.pk,
        starts_at=datetime(2026, 12, 25, tzinfo=timezone.utc),
        ends_at=datetime(2026, 12, 26, tzinfo=timezone.utc),
    )
    repository.create(
        branch_id=branch_b.pk,
        starts_at=datetime(2026, 12, 25, tzinfo=timezone.utc),
        ends_at=datetime(2026, 12, 26, tzinfo=timezone.utc),
    )

    result = repository.for_branch(branch_a.pk)

    assert [c.pk for c in result] == [wanted.pk]


@pytest.mark.django_db
def test_get_by_id_returns_none_when_missing():
    assert BranchClosureRepository().get_by_id(999_999) is None


@pytest.mark.django_db
def test_delete_removes_the_row():
    branch = BranchFactory()
    closure = BranchClosureRepository().create(
        branch_id=branch.pk,
        starts_at=datetime(2026, 12, 25, tzinfo=timezone.utc),
        ends_at=datetime(2026, 12, 26, tzinfo=timezone.utc),
    )
    closure_id = closure.pk

    BranchClosureRepository().delete(closure)

    assert BranchClosureRepository().get_by_id(closure_id) is None

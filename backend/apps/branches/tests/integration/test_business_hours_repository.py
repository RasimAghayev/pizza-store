from datetime import time

import pytest

from apps.branches.repositories.business_hours_repository import BusinessHoursRepository
from apps.branches.tests.factories import BranchFactory


@pytest.mark.django_db
def test_set_hours_creates_a_row():
    branch = BranchFactory()

    row = BusinessHoursRepository().set_hours(
        branch_id=branch.pk, weekday=0, opens_at=time(9, 0), closes_at=time(22, 0)
    )

    assert row.pk is not None
    assert row.weekday == 0


@pytest.mark.django_db
def test_set_hours_is_idempotent_per_weekday():
    branch = BranchFactory()
    repository = BusinessHoursRepository()
    repository.set_hours(branch_id=branch.pk, weekday=0, opens_at=time(9, 0), closes_at=time(22, 0))

    repository.set_hours(
        branch_id=branch.pk, weekday=0, opens_at=time(10, 0), closes_at=time(20, 0)
    )

    rows = repository.for_branch(branch.pk)
    assert len(rows) == 1
    assert rows[0].opens_at == time(10, 0)


@pytest.mark.django_db
def test_clear_day_removes_the_row():
    branch = BranchFactory()
    repository = BusinessHoursRepository()
    repository.set_hours(branch_id=branch.pk, weekday=0, opens_at=time(9, 0), closes_at=time(22, 0))

    repository.clear_day(branch_id=branch.pk, weekday=0)

    assert repository.for_branch(branch.pk) == []


@pytest.mark.django_db
def test_for_branch_returns_rows_ordered_by_weekday():
    branch = BranchFactory()
    repository = BusinessHoursRepository()
    repository.set_hours(branch_id=branch.pk, weekday=5, opens_at=time(9, 0), closes_at=time(22, 0))
    repository.set_hours(branch_id=branch.pk, weekday=1, opens_at=time(9, 0), closes_at=time(22, 0))

    weekdays = [row.weekday for row in repository.for_branch(branch.pk)]

    assert weekdays == [1, 5]

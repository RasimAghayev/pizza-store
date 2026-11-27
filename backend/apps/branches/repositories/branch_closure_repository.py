from datetime import datetime

from apps.branches.models import BranchClosure


class BranchClosureRepository:
    """Only file in this module allowed to issue an ORM query for BranchClosure, per ADR 0004."""

    def create(
        self, *, branch_id: int, starts_at: datetime, ends_at: datetime, reason: str = ""
    ) -> BranchClosure:
        return BranchClosure.objects.create(
            branch_id=branch_id, starts_at=starts_at, ends_at=ends_at, reason=reason
        )

    def for_branch(self, branch_id: int) -> list[BranchClosure]:
        return list(BranchClosure.objects.filter(branch_id=branch_id).order_by("starts_at"))

    def get_by_id(self, closure_id: int) -> BranchClosure | None:
        return BranchClosure.objects.filter(pk=closure_id).first()

    def delete(self, closure: BranchClosure) -> None:
        closure.delete()

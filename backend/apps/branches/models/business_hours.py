from django.db import models


class BusinessHours(models.Model):
    """One row per weekday a branch is open; `weekday` follows Python's `date.weekday()`
    convention (Monday=0 .. Sunday=6). A closed day is represented by the **absence** of a
    row for that weekday, not an `is_closed` flag -- chosen over a flag because it keeps
    `BranchService.is_open_now` a single lookup-and-compare with no extra null-handling branch
    for a day that doesn't apply (`branches/domain/opening_hours.py`)."""

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.CASCADE, related_name="business_hours"
    )
    weekday = models.PositiveSmallIntegerField()
    opens_at = models.TimeField()
    closes_at = models.TimeField()

    class Meta:
        app_label = "branches"
        constraints = [
            models.UniqueConstraint(fields=["branch", "weekday"], name="unique_branch_weekday")
        ]
        ordering = ["weekday"]

    def __str__(self) -> str:
        return f"{self.branch_id}:{self.weekday}"

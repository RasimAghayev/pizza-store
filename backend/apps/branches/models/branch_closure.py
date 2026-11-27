from django.db import models


class BranchClosure(models.Model):
    """A holiday/temporary closure as a time range (`starts_at`/`ends_at`), not a single flag
    -- lets a closure be scheduled in advance and auto-expire, per Issue #180's Implementation
    Prompt. Overlaps `BusinessHours` for the affected range: `is_open_now` always checks an
    active closure first regardless of what the weekly hours say."""

    branch = models.ForeignKey("branches.Branch", on_delete=models.CASCADE, related_name="closures")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        app_label = "branches"
        ordering = ["starts_at"]

    def __str__(self) -> str:
        return f"{self.branch_id}:{self.starts_at.isoformat()}"

from django.db import models


class Restaurant(models.Model):
    """A named concept under one `Organization` -- master prompt §11: "Restaurant and Branch/
    Location are separate entities." A `Restaurant` has no address/GPS/hours of its own; those
    live on `branches.Branch` (ADR 0006 Context)."""

    organization = models.ForeignKey(
        "restaurants.Organization", on_delete=models.CASCADE, related_name="restaurants"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "restaurants"

    def __str__(self) -> str:
        return self.name

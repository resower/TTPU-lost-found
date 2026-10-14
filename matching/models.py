from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .scoring import LABELS


class MatchSuggestion(models.Model):
    """'This found item might be that lost item.' Made by the worker, staff or the owner."""

    class CreatedBy(models.TextChoices):
        SYSTEM = "system", _("System")
        STAFF = "staff", _("Staff")
        USER = "user", _("Owner")

    class Status(models.TextChoices):
        SUGGESTED = "suggested", _("Suggested")
        CONFIRMED = "confirmed", _("Confirmed")
        REJECTED = "rejected", _("Rejected")

    lost_report = models.ForeignKey(
        "reports.LostReport", on_delete=models.CASCADE, related_name="suggestions"
    )
    # Exactly one of these two is set: an item on the shelf, or an item the finder kept.
    stored_item = models.ForeignKey(
        "storage.StoredItem",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="suggestions",
    )
    found_report = models.ForeignKey(
        "reports.FoundReport",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="suggestions",
    )
    score = models.PositiveSmallIntegerField()
    breakdown = models.JSONField(default=dict, blank=True)
    created_by = models.CharField(max_length=6, choices=CreatedBy.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUGGESTED)
    # What the owner answered in the bot: "yes", "no" or "" (no answer yet).
    reporter_answer = models.CharField(max_length=3, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # The database itself refuses a duplicate pair, even if the worker restarts mid-run.
            models.UniqueConstraint(
                fields=["lost_report", "stored_item"], name="unique_suggestion_per_stored_item"
            ),
            models.UniqueConstraint(
                fields=["lost_report", "found_report"], name="unique_suggestion_per_found_report"
            ),
            models.CheckConstraint(
                condition=(Q(stored_item__isnull=False) & Q(found_report__isnull=True))
                | (Q(stored_item__isnull=True) & Q(found_report__isnull=False)),
                name="suggestion_has_exactly_one_item",
            ),
        ]

    @property
    def item(self):
        return self.stored_item or self.found_report

    @property
    def explanation(self):
        """The breakdown as [(label, points)] for display."""
        return [(LABELS[key], points) for key, points in self.breakdown.items()]

    def __str__(self):
        return f"{self.lost_report} ~ {self.item} ({self.score})"

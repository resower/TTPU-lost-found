from datetime import timedelta

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

EXPIRING_SOON_DAYS = 7


def retention_date(received_at, category):
    """The last day the office keeps an item: arrival day plus the category's retention days."""
    return timezone.localtime(received_at).date() + timedelta(days=category.retention_days)


class StoredItem(models.Model):
    """The physical object on the office shelf.

    A FoundReport is only a claim that something was found. The office may receive items
    nobody reported (found_report is empty), and a finder may keep the item (no StoredItem).
    """

    class Status(models.TextChoices):
        IN_STORAGE = "in_storage", _("In storage")
        RETURNED = "returned", _("Returned")
        DISPOSED = "disposed", _("Disposed")
        TRANSFERRED = "transferred", _("Transferred")

    found_report = models.OneToOneField(
        "reports.FoundReport",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stored_item",
    )
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.ForeignKey(
        "catalog.Color", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    photo = models.ImageField(upload_to="items/", blank=True)
    shelf_code = models.CharField(max_length=10)
    received_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    retention_until = models.DateField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_STORAGE)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            # Two items on the shelf can never share a code. Returned items free their code.
            models.UniqueConstraint(
                fields=["shelf_code"],
                condition=models.Q(status="in_storage"),
                name="unique_shelf_code_in_storage",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.retention_until:
            self.retention_until = retention_date(self.received_at, self.category)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shelf_code} {self.title}"

    @property
    def search_text(self):
        return f"{self.title} {self.description}"

    # Where and when it was found: taken from the report if there is one.
    @property
    def found_location(self):
        return self.found_report.location if self.found_report else None

    @property
    def found_date(self):
        if self.found_report:
            return self.found_report.date_found
        return timezone.localtime(self.received_at).date()

    @property
    def ready_for_disposal(self):
        return self.status == self.Status.IN_STORAGE and self.retention_until < timezone.localdate()

    @property
    def expiring_soon(self):
        today = timezone.localdate()
        limit = today + timedelta(days=EXPIRING_SOON_DAYS)
        return self.status == self.Status.IN_STORAGE and today <= self.retention_until <= limit


class ItemStatusLog(models.Model):
    """Every status change of an item, never edited afterwards."""

    item = models.ForeignKey(StoredItem, on_delete=models.CASCADE, related_name="log")
    old_status = models.CharField(max_length=12, blank=True, choices=StoredItem.Status.choices)
    new_status = models.CharField(max_length=12, choices=StoredItem.Status.choices)
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=200, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["timestamp", "id"]


class Handover(models.Model):
    """The moment an item goes back to its owner. One item has at most one handover."""

    stored_item = models.OneToOneField(
        StoredItem, on_delete=models.PROTECT, related_name="handover"
    )
    lost_report = models.ForeignKey(
        "reports.LostReport",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handovers",
    )
    receiver_name = models.CharField(max_length=120)
    # Privacy: only the last 4 digits of the ID are ever stored.
    id_last4 = models.CharField(
        max_length=4, validators=[RegexValidator(r"^\d{4}$", "Enter exactly 4 digits.")]
    )
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    handed_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=200, blank=True)

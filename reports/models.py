from django.db import models
from django.utils.translation import gettext_lazy as _


class TelegramUser(models.Model):
    """A student or staff member who talks to the bot. Office staff are Django users instead."""

    class Language(models.TextChoices):
        UZ = "uz", "O'zbekcha"
        RU = "ru", "Русский"
        EN = "en", "English"

    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=64, blank=True)
    display_name = models.CharField(max_length=128)
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.UZ)
    student_staff_id = models.CharField(
        max_length=32, blank=True, help_text="Optional. Never enter a full ID number here."
    )
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name


class Report(models.Model):
    """Fields shared by lost and found reports."""

    reporter = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="%(class)ss")
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=100)
    description = models.TextField()
    color = models.ForeignKey("catalog.Color", on_delete=models.PROTECT, related_name="+")
    # We keep Telegram's file_id, not the picture itself (privacy + no storage cost).
    photo_file_id = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class LostReport(Report):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        MATCHED = "matched", _("Matched")
        RETURNED = "returned", _("Returned")
        EXPIRED = "expired", _("Expired")
        CANCELLED = "cancelled", _("Cancelled")

    marks = models.CharField(max_length=200, blank=True, help_text="Brand or distinctive marks.")
    location = models.ForeignKey(
        "catalog.Location",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lost_reports",
    )
    date_lost = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    # Set when the reporter reopens an expired report, so it is not expired again at once.
    reopened_at = models.DateTimeField(null=True, blank=True)

    @property
    def search_text(self):
        return f"{self.title} {self.description} {self.marks}"


class FoundReport(Report):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        REGISTERED = "registered", _("Registered")
        RETURNED = "returned", _("Returned")
        CANCELLED = "cancelled", _("Cancelled")

    location = models.ForeignKey(
        "catalog.Location", on_delete=models.PROTECT, related_name="found_reports"
    )
    date_found = models.DateField()
    # False: the item was handed to the office. True: the finder still has it.
    kept_by_finder = models.BooleanField(default=False)
    # The finder agreed that the owner may see their Telegram contact.
    share_contact = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    @property
    def search_text(self):
        return f"{self.title} {self.description}"

    # Same names as StoredItem uses, so matching code can treat both alike.
    @property
    def found_location(self):
        return self.location

    @property
    def found_date(self):
        return self.date_found

from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _


class Named(models.Model):
    """Reference data that has a name in each of the three languages."""

    name_uz = models.CharField(max_length=80)
    name_ru = models.CharField(max_length=80)
    name_en = models.CharField(max_length=80)

    class Meta:
        abstract = True

    def label(self, lang=None):
        """Name in the given language (default: the current web language)."""
        lang = (lang or get_language() or "uz")[:2]
        return getattr(self, f"name_{lang}", "") or self.name_en

    def __str__(self):
        return self.label()


class Category(Named):
    emoji = models.CharField(max_length=8)
    retention_days = models.PositiveIntegerField(
        help_text=_("How many days the office keeps an unclaimed item of this category.")
    )

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name_en"]


class Color(Named):
    class Meta:
        ordering = ["name_en"]


class Location(models.Model):
    """A campus place. Two levels: a building (no parent) and areas inside it."""

    name = models.CharField(max_length=120)
    floor = models.CharField(max_length=20, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="areas"
    )

    class Meta:
        ordering = ["parent__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="unique_location_in_building")
        ]

    @property
    def building(self):
        return self.parent or self

    def __str__(self):
        return f"{self.parent.name} / {self.name}" if self.parent else self.name

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Category, Location


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name", "floor", "parent"]
        labels = {"name": _("Name"), "floor": _("Floor"), "parent": _("Building")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only buildings can contain areas (two levels, no deeper).
        self.fields["parent"].queryset = Location.objects.filter(parent=None)
        self.fields["parent"].empty_label = _("— this is a building —")


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["emoji", "name_uz", "name_ru", "name_en", "retention_days"]
        labels = {
            "emoji": _("Emoji"),
            "name_uz": "O'zbekcha",
            "name_ru": "Русский",
            "name_en": "English",
            "retention_days": _("Retention (days)"),
        }

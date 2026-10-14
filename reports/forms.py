from django import forms
from django.utils.translation import gettext_lazy as _

from catalog.models import Category

from .models import LostReport


class LostFilterForm(forms.Form):
    q = forms.CharField(required=False, label=_("Search"))
    status = forms.ChoiceField(
        required=False,
        label=_("Status"),
        choices=[("", _("All"))] + LostReport.Status.choices,
    )
    category = forms.ModelChoiceField(
        required=False, label=_("Category"), queryset=Category.objects.all()
    )

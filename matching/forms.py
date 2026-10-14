from django import forms
from django.utils.translation import gettext_lazy as _

from storage.models import StoredItem


class PickItemForm(forms.Form):
    """Staff choose any item on the shelf as a match for a lost report."""

    stored_item = forms.ModelChoiceField(
        label=_("Item on the shelf"),
        queryset=StoredItem.objects.filter(status=StoredItem.Status.IN_STORAGE),
    )

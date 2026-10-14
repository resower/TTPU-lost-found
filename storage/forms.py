from django import forms
from django.utils.translation import gettext_lazy as _

from catalog.models import Category
from reports.models import FoundReport, LostReport

from .models import StoredItem


class ReceiveForm(forms.ModelForm):
    class Meta:
        model = StoredItem
        fields = [
            "found_report",
            "category",
            "title",
            "description",
            "color",
            "photo",
            "shelf_code",
        ]
        labels = {
            "found_report": _("Found report (if the finder reported it in the bot)"),
            "category": _("Category"),
            "title": _("Title"),
            "description": _("Description"),
            "color": _("Color"),
            "photo": _("Photo"),
            "shelf_code": _("Shelf code"),
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only reports that the office has not registered yet can be linked.
        self.fields["found_report"].queryset = FoundReport.objects.filter(
            status=FoundReport.Status.OPEN
        )
        self.fields["found_report"].required = False

    def clean_shelf_code(self):
        code = self.cleaned_data["shelf_code"].strip().upper()
        taken = StoredItem.objects.filter(shelf_code=code, status=StoredItem.Status.IN_STORAGE)
        if taken.exists():
            raise forms.ValidationError(_("This shelf code is already used by another item."))
        return code


class ReturnForm(forms.Form):
    lost_report = forms.ModelChoiceField(
        required=False,
        label=_("Matched lost report"),
        queryset=LostReport.objects.filter(
            status__in=[LostReport.Status.OPEN, LostReport.Status.MATCHED]
        ),
    )
    receiver_name = forms.CharField(max_length=120, label=_("Receiver name"))
    id_last4 = forms.RegexField(
        regex=r"^\d{4}$",
        max_length=4,
        min_length=4,
        label=_("Last 4 digits of the ID"),
        error_messages={"invalid": _("Enter exactly 4 digits.")},
    )
    note = forms.CharField(required=False, max_length=200, label=_("Note"))


class StatusForm(forms.Form):
    note = forms.CharField(required=False, max_length=200, label=_("Note"))


class StorageFilterForm(forms.Form):
    q = forms.CharField(required=False, label=_("Search"))
    category = forms.ModelChoiceField(
        required=False, label=_("Category"), queryset=Category.objects.all()
    )
    shelf = forms.CharField(required=False, label=_("Shelf"))
    status = forms.ChoiceField(
        required=False,
        label=_("Status"),
        choices=[("", _("All"))] + StoredItem.Status.choices,
    )
    date_from = forms.DateField(
        required=False, label=_("Received from"), widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        required=False, label=_("Received to"), widget=forms.DateInput(attrs={"type": "date"})
    )
    expiring = forms.BooleanField(required=False, label=_("Expiring within 7 days"))

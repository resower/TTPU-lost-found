from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _


class StaffLoginForm(AuthenticationForm):
    """Normal login form, but only staff accounts may sign in."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(_("This account is not office staff."), code="not_staff")

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from reports.models import LostReport

from . import services
from .forms import PickItemForm
from .models import MatchSuggestion


@require_POST
def confirm(request, pk):
    suggestion = get_object_or_404(MatchSuggestion, pk=pk)
    services.review_suggestion(suggestion, MatchSuggestion.Status.CONFIRMED, request.user)
    messages.success(request, _("Match confirmed."))
    return redirect("lost_detail", pk=suggestion.lost_report_id)


@require_POST
def reject(request, pk):
    suggestion = get_object_or_404(MatchSuggestion, pk=pk)
    services.review_suggestion(suggestion, MatchSuggestion.Status.REJECTED, request.user)
    messages.success(request, _("Match rejected."))
    return redirect("lost_detail", pk=suggestion.lost_report_id)


@require_POST
def pick(request, lost_id):
    """Staff pick a stored item by hand. The owner is told, like for an automatic match."""
    lost = get_object_or_404(LostReport, pk=lost_id)
    form = PickItemForm(request.POST)
    if form.is_valid():
        suggestion, created = services.create_suggestion(
            lost, form.cleaned_data["stored_item"], MatchSuggestion.CreatedBy.STAFF
        )
        if created:
            services.notify_match(suggestion)
            messages.success(request, _("Match suggestion added."))
        else:
            messages.info(request, _("This item is already suggested for this report."))
    return redirect("lost_detail", pk=lost.pk)

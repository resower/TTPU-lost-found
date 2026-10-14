import re

from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from bot.notify import fetch_photo
from matching.forms import PickItemForm

from .forms import LostFilterForm
from .models import LostReport


def lost_list(request):
    # Open reports by default; choose "All" to see everything.
    form = LostFilterForm(request.GET or {"status": LostReport.Status.OPEN})
    reports = LostReport.objects.select_related("category", "color", "location", "reporter")
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            reports = reports.filter(
                Q(title__icontains=data["q"]) | Q(description__icontains=data["q"])
            )
        if data["status"]:
            reports = reports.filter(status=data["status"])
        if data["category"]:
            reports = reports.filter(category=data["category"])
    return render(request, "reports/lost_list.html", {"form": form, "reports": reports})


def lost_detail(request, pk):
    report = get_object_or_404(
        LostReport.objects.select_related("category", "color", "location", "reporter"), pk=pk
    )
    suggestions = report.suggestions.select_related(
        "stored_item", "found_report", "reviewed_by"
    ).order_by("-score")
    return render(
        request,
        "reports/lost_detail.html",
        {"report": report, "suggestions": suggestions, "pick_form": PickItemForm()},
    )


def telegram_photo(request, file_id):
    """Show a photo that only exists in Telegram: download once, then serve from the cache."""
    if not re.fullmatch(r"[\w-]+", file_id):
        raise Http404
    path = fetch_photo(file_id)
    if path is None:
        raise Http404
    return FileResponse(open(path, "rb"), content_type="image/jpeg")

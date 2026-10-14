import csv
from collections import Counter
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from catalog.models import Category, Location
from matching.models import MatchSuggestion
from reports.models import FoundReport, LostReport

from . import services
from .forms import ReceiveForm, ReturnForm, StatusForm, StorageFilterForm
from .models import EXPIRING_SOON_DAYS, Handover, StoredItem


def dashboard(request):
    today = timezone.localdate()
    in_storage = StoredItem.objects.filter(status=StoredItem.Status.IN_STORAGE)
    soon = today + timedelta(days=EXPIRING_SOON_DAYS)
    stats = {
        "in_storage": in_storage.count(),
        "expiring": in_storage.filter(retention_until__range=(today, soon)).count(),
        "ready_for_disposal": in_storage.filter(retention_until__lt=today).count(),
        "open_lost": LostReport.objects.filter(status=LostReport.Status.OPEN).count(),
        "pending_matches": MatchSuggestion.objects.filter(
            status=MatchSuggestion.Status.SUGGESTED
        ).count(),
        "returned_month": Handover.objects.filter(
            handed_at__year=today.year, handed_at__month=today.month
        ).count(),
    }

    # Chart 1: items in storage by category.
    category_names = {c.id: c.label() for c in Category.objects.all()}
    per_category = in_storage.values("category").annotate(n=Count("id")).order_by("-n")
    by_category = {
        "labels": [category_names[row["category"]] for row in per_category],
        "values": [row["n"] for row in per_category],
    }

    # Chart 2: the 10 locations with the most reports (lost and found together).
    per_location = Counter()
    for model in (LostReport, FoundReport):
        rows = model.objects.exclude(location=None).values("location").annotate(n=Count("id"))
        for row in rows:
            per_location[row["location"]] += row["n"]
    top = per_location.most_common(10)
    names = {loc.id: str(loc) for loc in Location.objects.filter(id__in=[i for i, _n in top])}
    by_location = {"labels": [names[i] for i, _n in top], "values": [n for _i, n in top]}

    return render(
        request,
        "storage/dashboard.html",
        {"stats": stats, "by_category": by_category, "by_location": by_location},
    )


def storage_list(request):
    # Items in storage by default; choose "All" to see returned and disposed ones too.
    form = StorageFilterForm(request.GET or {"status": StoredItem.Status.IN_STORAGE})
    items = StoredItem.objects.select_related("category", "color")
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            items = items.filter(
                Q(title__icontains=data["q"])
                | Q(description__icontains=data["q"])
                | Q(shelf_code__icontains=data["q"])
            )
        if data["category"]:
            items = items.filter(category=data["category"])
        if data["shelf"]:
            items = items.filter(shelf_code__istartswith=data["shelf"])
        if data["status"]:
            items = items.filter(status=data["status"])
        if data["date_from"]:
            items = items.filter(received_at__date__gte=data["date_from"])
        if data["date_to"]:
            items = items.filter(received_at__date__lte=data["date_to"])
        if data["expiring"]:
            today = timezone.localdate()
            soon = today + timedelta(days=EXPIRING_SOON_DAYS)
            items = items.filter(retention_until__range=(today, soon))
    return render(request, "storage/list.html", {"form": form, "items": items})


def storage_detail(request, pk):
    item = get_object_or_404(StoredItem.objects.select_related("category", "color"), pk=pk)
    return render(
        request,
        "storage/detail.html",
        {
            "item": item,
            "log": item.log.select_related("staff"),
            "suggestions": item.suggestions.select_related("lost_report").order_by("-score"),
            "status_form": StatusForm(),
        },
    )


def receive_item(request):
    open_reports = FoundReport.objects.filter(status=FoundReport.Status.OPEN).select_related(
        "category"
    )
    if request.method == "POST":
        form = ReceiveForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.received_by = request.user
            services.register_item(item)
            messages.success(
                request, _("Item saved on shelf %(code)s.") % {"code": item.shelf_code}
            )
            return redirect("storage_detail", pk=item.pk)
    else:
        # ?found=<id> pre-fills the form from the finder's report.
        initial = {"shelf_code": services.next_free_shelf_code()}
        report = open_reports.filter(pk=request.GET.get("found") or 0).first()
        if report:
            initial.update(
                found_report=report,
                category=report.category,
                title=report.title,
                description=report.description,
                color=report.color,
            )
        form = ReceiveForm(initial=initial)
    return render(request, "storage/receive.html", {"form": form, "open_reports": open_reports})


def return_item(request, pk):
    item = get_object_or_404(StoredItem, pk=pk, status=StoredItem.Status.IN_STORAGE)
    if request.method == "POST":
        form = ReturnForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            services.return_item(
                item,
                request.user,
                data["receiver_name"],
                data["id_last4"],
                lost_report=data["lost_report"],
                note=data["note"],
            )
            messages.success(request, _("The item was handed over."))
            return redirect("storage_detail", pk=item.pk)
    else:
        # Pre-select the lost report that staff already confirmed for this item.
        confirmed = item.suggestions.filter(status=MatchSuggestion.Status.CONFIRMED).first()
        form = ReturnForm(initial={"lost_report": confirmed.lost_report if confirmed else None})
    return render(request, "storage/return.html", {"item": item, "form": form})


@require_POST
def change_status(request, pk):
    item = get_object_or_404(StoredItem, pk=pk)
    action = request.POST.get("action")
    new_status = {
        "dispose": StoredItem.Status.DISPOSED,
        "transfer": StoredItem.Status.TRANSFERRED,
    }.get(action)
    form = StatusForm(request.POST)
    if new_status and form.is_valid():
        try:
            services.change_status(item, new_status, request.user, form.cleaned_data["note"])
            messages.success(request, _("Status updated."))
        except services.InvalidTransition as error:
            messages.error(request, str(error))
    return redirect("storage_detail", pk=item.pk)


def export_csv(request):
    """Items currently in storage, for the monthly inventory."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="items-in-storage.csv"'
    writer = csv.writer(response)
    writer.writerow(["shelf", "category", "title", "color", "received", "keep until"])
    items = StoredItem.objects.filter(status=StoredItem.Status.IN_STORAGE).order_by("shelf_code")
    for item in items.select_related("category", "color"):
        writer.writerow(
            [
                item.shelf_code,
                item.category.label("en"),
                item.title,
                item.color.label("en") if item.color else "",
                timezone.localtime(item.received_at).strftime("%Y-%m-%d"),
                item.retention_until.isoformat(),
            ]
        )
    return response


def media_file(request, path):
    """Uploaded photos are private: only logged-in staff can open them (see the middleware)."""
    root = Path(settings.MEDIA_ROOT).resolve()
    full = (root / path).resolve()
    if root not in full.parents or not full.is_file():
        raise Http404
    return FileResponse(open(full, "rb"))

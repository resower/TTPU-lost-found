from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, UpdateView

from .forms import CategoryForm, LocationForm
from .models import Category, Location


def reference(request):
    """Locations and categories on one page, with links to the forms."""
    return render(
        request,
        "catalog/reference.html",
        {
            "buildings": Location.objects.filter(parent=None).prefetch_related("areas"),
            "categories": Category.objects.all(),
        },
    )


class ReferenceFormMixin:
    template_name = "catalog/form.html"
    success_url = reverse_lazy("reference")


class LocationCreate(ReferenceFormMixin, CreateView):
    form_class = LocationForm
    extra_context = {"title": _("New location")}


class LocationUpdate(ReferenceFormMixin, UpdateView):
    model = Location
    form_class = LocationForm
    extra_context = {"title": _("Edit location")}


class CategoryCreate(ReferenceFormMixin, CreateView):
    form_class = CategoryForm
    extra_context = {"title": _("New category")}


class CategoryUpdate(ReferenceFormMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    extra_context = {"title": _("Edit category")}

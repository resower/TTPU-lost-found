from django.urls import path

from . import views

urlpatterns = [
    path("reference/", views.reference, name="reference"),
    path("locations/new/", views.LocationCreate.as_view(), name="location_new"),
    path("locations/<int:pk>/edit/", views.LocationUpdate.as_view(), name="location_edit"),
    path("categories/new/", views.CategoryCreate.as_view(), name="category_new"),
    path("categories/<int:pk>/edit/", views.CategoryUpdate.as_view(), name="category_edit"),
]

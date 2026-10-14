from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("receive/", views.receive_item, name="receive_item"),
    path("storage/", views.storage_list, name="storage_list"),
    path("storage/export.csv", views.export_csv, name="export_csv"),
    path("storage/<int:pk>/", views.storage_detail, name="storage_detail"),
    path("storage/<int:pk>/return/", views.return_item, name="return_item"),
    path("storage/<int:pk>/status/", views.change_status, name="change_status"),
    path("media/<path:path>", views.media_file, name="media_file"),
]

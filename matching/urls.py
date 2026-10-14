from django.urls import path

from . import views

urlpatterns = [
    path("matches/<int:pk>/confirm/", views.confirm, name="match_confirm"),
    path("matches/<int:pk>/reject/", views.reject, name="match_reject"),
    path("lost/<int:lost_id>/pick/", views.pick, name="match_pick"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("lost/", views.lost_list, name="lost_list"),
    path("lost/<int:pk>/", views.lost_detail, name="lost_detail"),
    path("tg-photo/<str:file_id>/", views.telegram_photo, name="tg_photo"),
]

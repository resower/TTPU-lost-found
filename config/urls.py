from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

from .forms import StaffLoginForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        LoginView.as_view(template_name="login.html", authentication_form=StaffLoginForm),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", include("storage.urls")),
    path("", include("reports.urls")),
    path("", include("matching.urls")),
    path("", include("catalog.urls")),
]

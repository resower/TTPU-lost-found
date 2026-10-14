from django.contrib.auth.views import redirect_to_login

# The login page, static files and the admin (which has its own login) stay open.
OPEN_PREFIXES = ("/login/", "/static/", "/admin/")


class StaffRequiredMiddleware:
    """The whole web app is the back office: only logged-in staff may open a page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        is_staff = user.is_authenticated and user.is_staff
        if not is_staff and not request.path.startswith(OPEN_PREFIXES):
            return redirect_to_login(request.get_full_path())
        return self.get_response(request)

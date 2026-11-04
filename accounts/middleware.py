from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import Resolver404, resolve

from .access import admin_section_for, home_url_for, staff_feature_enabled, staff_feature_for
from .models import User

# Pages anyone may open without logging in.
PUBLIC_PATHS = {"/", "/logout/", "/setup-admin/", "/staff/register/"}

# Each area of the site belongs to one or more roles. Every page under the
# prefix is checked here, so a page that forgets its own check is still protected.
AREA_ROLES = (
    ("/super/", (User.SUPER_ADMIN,)),
    ("/admin/", (User.SUPER_ADMIN, User.ADMIN)),
    ("/staff/", (User.STAFF,)),
)


class RoleAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path not in PUBLIC_PATHS:
            for prefix, roles in AREA_ROLES:
                if path.startswith(prefix):
                    return self.check_access(request, roles)
        return self.get_response(request)

    def check_access(self, request, roles):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if user.role not in roles:
            raise PermissionDenied
        if user.role == User.STAFF and not user.is_approved:
            raise PermissionDenied

        reason = self.switched_off_reason(request, user)
        if reason:
            return render(
                request,
                "accounts/access_denied.html",
                {"reason": reason, "home_url": home_url_for(user)},
                status=403,
            )
        return self.get_response(request)

    def switched_off_reason(self, request, user):
        """Why this page is closed for this user by a Super Admin setting, or None."""
        try:
            url_name = resolve(request.path_info).url_name
        except Resolver404:
            return None

        if user.role == User.ADMIN:
            section = admin_section_for(url_name)
            if section and section in (user.blocked_sections or []):
                return "A Super Admin has turned this part of the admin area off for your account."

        if user.role == User.STAFF:
            feature = staff_feature_for(url_name)
            if feature and not staff_feature_enabled(feature):
                return "A Super Admin has turned this feature off for all staff."

        return None

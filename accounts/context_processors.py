from admin_panel.nav import build_admin_nav

from .access import ADMIN_ROLES, Permissions


def access(request):
    """Adds `can` (what this user may open) and, for admins, the sidebar `nav_groups`."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    can = Permissions(user)
    context = {"can": can}
    if user.role in ADMIN_ROLES:
        context["nav_groups"] = build_admin_nav(can)
    return context

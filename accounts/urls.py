from django.urls import path

from . import views

urlpatterns = [
    path("", views.RoleLoginView.as_view(), name="login"),
    path("setup-admin/", views.setup_admin, name="setup_admin"),

    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("staff/register/", views.staff_register, name="staff_register"),

    path("google/", views.google_login, name="google_login"),
    path("google/callback/", views.google_callback, name="google_callback"),
]

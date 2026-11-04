import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView as DjangoLogoutView
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from . import google_auth
from .access import home_url_for
from .forms import ApprovedAuthenticationForm, FirstAdminForm, StaffRegistrationForm
from .models import User

# Holds the one-time state and nonce while a Google sign-in is in progress.
GOOGLE_SESSION_KEY = "google_sign_in"


def setup_admin(request):
    # The page disappears once an admin exists.
    if User.objects.filter(role__in=(User.SUPER_ADMIN, User.ADMIN)).exists():
        raise Http404("Setup is no longer available.")

    if request.method == "POST":
        form = FirstAdminForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.role = User.ADMIN
            user.save()

            login(request, user)
            return redirect("admin_dashboard")
    else:
        form = FirstAdminForm()

    return render(request, "accounts/setup_admin.html", {"form": form})

def staff_register(request):
    if request.method == "POST":
        form = StaffRegistrationForm(request.POST)

        if form.is_valid():
            form.save()
            return render(request, "accounts/registration_waiting.html")
    else:
        form = StaffRegistrationForm()

    return render(request, "accounts/staff_register.html", {
        "form": form,
        "google_enabled": google_auth.is_configured(),
    })


class RoleLoginView(LoginView):
    """One login page for admins and staff. Each user goes to their own area."""

    template_name = "accounts/login.html"
    authentication_form = ApprovedAuthenticationForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        # Used when the login link has no ?next= address.
        return home_url_for(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["google_enabled"] = google_auth.is_configured()
        return context


class LogoutView(DjangoLogoutView):
    """Django only logs out on POST. The sidebar links are plain links (GET)."""

    next_page = "login"
    http_method_names = ["get", "post", "options"]

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


# ---------------------------------------------------------------
# Sign in with Google
# ---------------------------------------------------------------

def _google_redirect_uri(request):
    # GOOGLE_REDIRECT_URI pins the exact address; otherwise it is built from this request.
    return settings.GOOGLE_REDIRECT_URI or request.build_absolute_uri(reverse("google_callback"))


def google_login(request):
    if not google_auth.is_configured():
        messages.error(request, "Google sign-in is not set up yet. Please use your username and password.")
        return redirect("login")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    request.session[GOOGLE_SESSION_KEY] = {"state": state, "nonce": nonce}
    return redirect(google_auth.build_auth_url(_google_redirect_uri(request), state, nonce))


def google_callback(request):
    # The saved state and nonce are used once, whatever the outcome.
    saved = request.session.pop(GOOGLE_SESSION_KEY, None)

    if request.GET.get("error"):
        messages.error(request, "Google sign-in was cancelled.")
        return redirect("login")

    if not google_auth.is_configured() or not saved:
        messages.error(request, "That Google sign-in link has expired. Please try again.")
        return redirect("login")

    returned_state = request.GET.get("state", "").encode()
    if not secrets.compare_digest(returned_state, saved.get("state", "").encode()):
        messages.error(request, "That Google sign-in link has expired. Please try again.")
        return redirect("login")

    try:
        token = google_auth.exchange_code(request.GET.get("code", ""), _google_redirect_uri(request))
        claims = google_auth.check_claims(google_auth.read_claims(token), saved.get("nonce", ""))
    except google_auth.GoogleAuthError as error:
        messages.error(request, str(error))
        return redirect("login")

    return _sign_in_with_google(request, claims)


def _sign_in_with_google(request, claims):
    email = claims["email"].strip()
    user = User.objects.filter(email__iexact=email).first()

    if user is None:
        # A new Google user starts as an unapproved staff member, the same as the registration form.
        User.objects.create_user(
            username=_free_username(email),
            email=email,
            full_name=(claims.get("name") or "")[:150],
            role=User.STAFF,
            is_approved=False,
        )
        return render(request, "accounts/registration_waiting.html")

    if not user.is_active:
        messages.error(request, "This account is disabled. Please contact the administrator.")
        return redirect("login")

    if user.role == User.STAFF and not user.is_approved:
        return render(request, "accounts/registration_waiting.html")

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(home_url_for(user))


def _free_username(email):
    # Same rule as the registration form: the email address is the username.
    base = email[:140]
    username, number = base, 1
    while User.objects.filter(username=username).exists():
        number += 1
        username = f"{base}-{number}"
    return username

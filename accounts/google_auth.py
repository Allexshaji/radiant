"""Sign in with Google (OpenID Connect, authorization-code flow).

Only Python's standard library is used, so nothing new has to be installed.

1. google_login sends the user to Google with a random `state` and `nonce`.
2. Google sends the user back to google_callback with a one-time `code`.
3. We trade that code for an id_token directly with Google, over HTTPS,
   and check the token's claims: issuer, audience, expiry, nonce and a
   verified email address.
"""
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
ISSUERS = ("accounts.google.com", "https://accounts.google.com")
TIMEOUT_SECONDS = 10


class GoogleAuthError(Exception):
    """Google sign-in could not be completed safely. The message is shown to the user."""


def is_configured():
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def build_auth_url(redirect_uri, state, nonce):
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
    }
    return AUTH_ENDPOINT + "?" + urllib.parse.urlencode(params)


def exchange_code(code, redirect_uri):
    """Trade the one-time code for an id_token. This is a server-to-server call."""
    body = urllib.parse.urlencode({
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, ValueError) as exc:
        raise GoogleAuthError("Could not reach Google. Please try again.") from exc

    token = payload.get("id_token")
    if not token:
        raise GoogleAuthError("Google did not return an identity. Please try again.")
    return token


def read_claims(id_token):
    """Return the claims inside an id_token.

    The token arrives directly from Google over HTTPS, so OpenID Connect allows
    us to skip the signature check and rely on the TLS connection instead.
    """
    try:
        middle = id_token.split(".")[1]
        padded = middle + "=" * (-len(middle) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (IndexError, ValueError) as exc:
        raise GoogleAuthError("Google sent an identity that could not be read.") from exc


def check_claims(claims, expected_nonce):
    """Refuse the sign-in unless every claim we rely on is right."""
    if claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("The identity did not come from Google.")
    if claims.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise GoogleAuthError("This Google identity was issued for a different app.")
    if claims.get("exp", 0) < time.time():
        raise GoogleAuthError("The Google sign-in expired. Please try again.")
    if not expected_nonce or claims.get("nonce") != expected_nonce:
        raise GoogleAuthError("The Google sign-in could not be verified. Please try again.")
    if claims.get("email_verified") not in (True, "true"):
        raise GoogleAuthError("Your Google email address is not verified.")
    if not claims.get("email"):
        raise GoogleAuthError("Google did not share an email address.")
    return claims

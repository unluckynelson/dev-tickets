"""Playground sign-in: pick a person, no password. DEBUG-only, never copy this into an app."""

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import Http404, HttpResponse

BOARD = "/admin/dev-tickets"


def _to_board() -> HttpResponse:
    # Not a 302: the Nuxt dev proxy follows redirects itself, so the browser would get
    # Django's 404 for the board instead of the app, and lose the session cookie.
    return HttpResponse(
        f'<!doctype html><meta http-equiv="refresh" content="0;url={BOARD}">'
    )


def people(request):
    if not settings.DEBUG:
        raise Http404
    rows = "".join(
        f'<li><a href="/playground/login/{u.username}/">{u.get_full_name()}</a></li>'
        for u in get_user_model().objects.order_by("first_name")
    )
    return HttpResponse(
        "<!doctype html><meta charset=utf-8><title>Playground sign-in</title>"
        "<body style='font-family:system-ui;max-width:28rem;margin:4rem auto'>"
        f"<h1>Sign in as</h1><ul>{rows}</ul>"
        '<p><a href="/playground/logout/">Sign out</a> (to see what an outsider sees)</p>'
    )


def login_as(request, username):
    if not settings.DEBUG:
        raise Http404
    user = get_user_model().objects.filter(username=username).first()
    if user is None:
        raise Http404
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return _to_board()


def logout_view(request):
    logout(request)
    return _to_board()

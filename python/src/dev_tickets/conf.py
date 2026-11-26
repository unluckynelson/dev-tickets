"""Settings, read from one `DEV_TICKETS` dict in the host's settings.

Every value is read when it is used, not at import, so `override_settings` and
pytest-django's `settings` fixture work without reloading anything.

`STORED` settings (the mode and how a client reaches its hub) can also be set from
the board's Settings dialog, kept in `TrackerSettings`. The host's value wins when
it sets one, and the dialog shows that field as locked (`locked`). The hooks
(`CAN_ACCESS`, `TEAM`, ...) take a callable or a dotted path to one; a dotted path
is imported on first use, so a host module that imports these models can be named.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

DEFAULTS: dict[str, Any] = {
    # standalone: tickets in this database, for this install's users.
    # hub: the same, and other installs reach the board through the API (`hub.py`).
    # client: no tickets here; every request is forwarded to the hub (`client.py`).
    "MODE": "standalone",
    # Identifier prefix: DEV-12.
    "PREFIX": "DEV",
    # What the board calls the team ("<team> tickets").
    "TEAM_NAME": "Dev",
    # Absolute URL of the board; email links are BOARD_URL + "/" + identifier.
    "BOARD_URL": "",
    # (user) -> bool. Who may see the board, file tickets and hold one.
    "CAN_ACCESS": "dev_tickets.defaults.can_access",
    # (user) -> bool. Who may change the mode and hub connection in Settings.
    # None: whoever passes CAN_ACCESS.
    "CAN_CONFIGURE": None,
    # () -> QuerySet of users who can be assigned a ticket.
    "TEAM": "dev_tickets.defaults.team",
    # (request) -> str. The company / workspace a ticket was filed from.
    "CONTEXT_LABEL": None,
    # (description, request) -> str. None: the description's first line.
    "TITLE_GENERATOR": None,
    # (subject, text, html, to) -> None. Default: Django's EmailMultiAlternatives.
    "SEND_MAIL": "dev_tickets.defaults.send_mail",
    # Seconds a notification stays unread before it is emailed.
    "EMAIL_AFTER": 120,
    # Name of the STORAGES entry attachments are kept in.
    "STORAGE": "default",
    "MAX_ATTACHMENT_MB": 15,
    # Username or email new tickets are assigned to when the reporter names nobody.
    "DEFAULT_ASSIGNEE": None,
    # client mode: the hub's base URL, this environment's key (`devtickets_client add`
    # on the hub prints it) and its name, shown on the hub as "from <SOURCE>".
    "HUB_URL": None,
    "HUB_API_KEY": None,
    "SOURCE": None,
    # client mode: seconds to wait for the hub before giving up.
    "HUB_TIMEOUT": 10,
    # (user) -> str | None. A picture of the user, sent to the hub with each request.
    "AVATAR": None,
}

# Settings a client cannot run without.
CLIENT_REQUIRED = ("HUB_URL", "HUB_API_KEY", "SOURCE")

MODES = ("standalone", "hub", "client")

# Settings the Settings dialog may set, and the `TrackerSettings` field each lives in.
STORED = {"MODE": "mode", "HUB_URL": "hub_url", "HUB_API_KEY": "hub_api_key", "SOURCE": "source"}

_TTL = 1.0
_stored: tuple[float, dict[str, str]] | None = None


def _host() -> dict:
    return getattr(settings, "DEV_TICKETS", {})


def clear_cache(*_args, **_kwargs) -> None:
    global _stored
    _stored = None


def _stored_values() -> dict[str, str]:
    """The Settings dialog's values, cached for a request (cleared on request start
    and on save). Empty before the table exists, e.g. during the first migrate."""
    global _stored
    now = time.monotonic()
    if _stored is not None and now - _stored[0] < _TTL:
        return _stored[1]
    from django.db import DatabaseError

    try:
        from .models import TrackerSettings

        row = TrackerSettings.objects.order_by("pk").first()
    except DatabaseError:
        row = None
    values = (
        {name: (getattr(row, field) or "").strip() for name, field in STORED.items()}
        if row else {}
    )  # fmt: skip
    _stored = (now, values)
    return values


def locked(name: str) -> bool:
    """True when the host's settings fix this value, so the dialog cannot change it."""
    return name in _host()


def get(name: str) -> Any:
    if name not in DEFAULTS:
        raise KeyError(f"Unknown DEV_TICKETS setting {name!r}.")
    host = _host()
    if name in host:
        return host[name]
    if name in STORED:
        value = _stored_values().get(name)
        if value:
            return value
    return DEFAULTS[name]


def hook(name: str) -> Callable | None:
    """A hook setting as a callable, or None when it is unset."""
    value = get(name)
    if value is None or value == "":
        return None
    if callable(value):
        return value
    try:
        return import_string(value)
    except ImportError as exc:
        raise ImproperlyConfigured(f"DEV_TICKETS[{name!r}] = {value!r}: {exc}") from exc


def check() -> None:
    """The host's own settings, at startup. Values from the Settings dialog are
    checked when they are saved instead (this runs before the database is ready)."""
    host = _host()
    unknown = set(host) - set(DEFAULTS)
    if unknown:
        raise ImproperlyConfigured(f"Unknown DEV_TICKETS settings: {', '.join(sorted(unknown))}.")
    if "MODE" not in host:
        return
    mode = host["MODE"]
    if mode not in MODES:
        raise ImproperlyConfigured(f"DEV_TICKETS['MODE'] must be one of {', '.join(MODES)}.")
    if mode == "client":
        missing = [name for name in CLIENT_REQUIRED if not str(host.get(name) or "").strip()]
        if missing:
            raise ImproperlyConfigured(
                "DEV_TICKETS['MODE'] = 'client' needs "
                + ", ".join(f"DEV_TICKETS[{name!r}]" for name in missing)
                + "."
            )
        url = str(host.get("HUB_URL"))
        if not url.startswith(("http://", "https://")):
            raise ImproperlyConfigured(
                f"DEV_TICKETS['HUB_URL'] = {url!r} must start with http:// or https://."
            )


def mode() -> str:
    return str(get("MODE"))

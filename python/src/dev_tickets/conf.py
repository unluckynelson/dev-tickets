"""Settings, read from one `DEV_TICKETS` dict in the host's settings.

Every value is read when it is used, not at import, so `override_settings` and
pytest-django's `settings` fixture work without reloading anything. The hooks
(`CAN_ACCESS`, `TEAM`, ...) take a callable or a dotted path to one; a dotted path
is imported on first use, so a host module that imports these models can be named.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

DEFAULTS: dict[str, Any] = {
    # standalone: tickets in this database. hub / client: planned, not built yet.
    "MODE": "standalone",
    # Identifier prefix: DEV-12.
    "PREFIX": "DEV",
    # What the board calls the team ("<team> tickets").
    "TEAM_NAME": "Dev",
    # Absolute URL of the board; email links are BOARD_URL + "/" + identifier.
    "BOARD_URL": "",
    # (user) -> bool. Who may see the board, file tickets and hold one.
    "CAN_ACCESS": "dev_tickets.defaults.can_access",
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
    # client mode (planned): the hub's base URL, this environment's key and its name.
    "HUB_URL": None,
    "HUB_API_KEY": None,
    "SOURCE": None,
}

MODES = ("standalone", "hub", "client")


def get(name: str) -> Any:
    if name not in DEFAULTS:
        raise KeyError(f"Unknown DEV_TICKETS setting {name!r}.")
    return getattr(settings, "DEV_TICKETS", {}).get(name, DEFAULTS[name])


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
    unknown = set(getattr(settings, "DEV_TICKETS", {})) - set(DEFAULTS)
    if unknown:
        raise ImproperlyConfigured(f"Unknown DEV_TICKETS settings: {', '.join(sorted(unknown))}.")
    mode = get("MODE")
    if mode not in MODES:
        raise ImproperlyConfigured(f"DEV_TICKETS['MODE'] must be one of {', '.join(MODES)}.")
    if mode != "standalone":
        raise ImproperlyConfigured(f"DEV_TICKETS['MODE'] = {mode!r} is not implemented yet.")

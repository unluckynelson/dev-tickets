"""The Settings dialog's Connection section: this install's mode, the hub it uses as a
client, and, as a hub, the keys other installs reach it with.

Plain JSON views under `devtickets/settings/`, never the GraphQL endpoint: in client
mode GraphQL is forwarded to the hub, and these must act on *this* install. Only a
local signed-in user who passes `CAN_CONFIGURE` may use them; a hub client's actor
never reaches them.

What the host fixes in `DEV_TICKETS` is shown and cannot be changed here
(`conf.locked`). A client connection is tried before it is saved (`client.probe`), so a
typo cannot leave the board unreachable.
"""

from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import client, conf, hub
from .models import HubClient, TrackerSettings
from .permissions import can_configure

LOCKABLE = {"mode": "MODE", "hubUrl": "HUB_URL", "hubApiKey": "HUB_API_KEY", "source": "SOURCE"}


def _refuse(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "message": message}, status=status)


def _guarded(view):
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not getattr(request.user, "is_authenticated", False):
            return _refuse("Authentication required.", 401)
        if not can_configure(request.user):
            return _refuse("You may not change the dev-tickets connection.", 403)
        return view(request, *args, **kwargs)

    wrapped.__name__ = view.__name__
    return wrapped


def _body(request: HttpRequest) -> dict:
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _client_row(c: HubClient) -> dict:
    return {
        "id": str(c.pk),
        "name": c.name,
        "source": c.source,
        "keyPrefix": c.key_prefix,
        "readOnly": c.read_only,
        "lastUsedAt": c.last_used_at.isoformat() if c.last_used_at else None,
        "revokedAt": c.revoked_at.isoformat() if c.revoked_at else None,
    }


def _state() -> dict:
    key = str(conf.get("HUB_API_KEY") or "")
    mode = conf.mode()
    return {
        "ok": True,
        "mode": mode,
        "modes": list(conf.MODES),
        "hubUrl": str(conf.get("HUB_URL") or ""),
        "source": str(conf.get("SOURCE") or ""),
        "hasKey": bool(key),
        # Enough to tell keys apart (the hub lists the same prefix), never the key.
        "keyHint": key[:8] if len(key) > 16 else "",
        "locked": {field: conf.locked(name) for field, name in LOCKABLE.items()},
        "clients": [_client_row(c) for c in HubClient.objects.all()] if mode == "hub" else [],
    }


@require_http_methods(["GET"])
@_guarded
def settings_state(request: HttpRequest) -> JsonResponse:
    return JsonResponse(_state())


def _resolve(data: dict) -> tuple[str, str, str]:
    """The URL, key and source a client connection would use: what was typed, else
    what is saved (a blank key field keeps the saved key)."""
    url = str(data.get("hubUrl") or "").strip() if not conf.locked("HUB_URL") else ""
    key = str(data.get("hubApiKey") or "").strip() if not conf.locked("HUB_API_KEY") else ""
    source = str(data.get("source") or "").strip() if not conf.locked("SOURCE") else ""
    return (
        url or str(conf.get("HUB_URL") or ""),
        key or str(conf.get("HUB_API_KEY") or ""),
        source or str(conf.get("SOURCE") or ""),
    )


@require_http_methods(["POST"])
@_guarded
def test_connection(request: HttpRequest) -> JsonResponse:
    url, key, _source = _resolve(_body(request))
    if not url.startswith(("http://", "https://")) or not key:
        return _refuse("Enter the hub's address (https://...) and this environment's key.")
    return JsonResponse(client.probe(request, url, key))


@require_http_methods(["POST"])
@_guarded
def save_connection(request: HttpRequest) -> JsonResponse:
    data = _body(request)
    row = TrackerSettings.load()
    mode = str(data.get("mode") or "").strip()
    if conf.locked("MODE") and mode and mode != conf.mode():
        return _refuse("The mode is set in this app's settings and cannot be changed here.")
    if not conf.locked("MODE"):
        if mode not in conf.MODES:
            return _refuse(f"Mode must be one of {', '.join(conf.MODES)}.")
        row.mode = mode
    mode = mode if not conf.locked("MODE") else conf.mode()
    if mode == "client":
        url, key, source = _resolve(data)
        if not url.startswith(("http://", "https://")):
            return _refuse("The hub's address must start with http:// or https://.")
        if not key:
            return _refuse("Enter the key the hub gave this environment.")
        if not source:
            return _refuse("Name this environment (e.g. staging), as the hub will show it.")
        tried = client.probe(request, url, key)
        if not tried["ok"]:
            return _refuse(f"Not saved: {tried['message']}")
        if not conf.locked("HUB_URL"):
            row.hub_url = url
        if not conf.locked("HUB_API_KEY"):
            row.hub_api_key = key
        if not conf.locked("SOURCE"):
            row.source = source[:60]
    row.save()
    conf.clear_cache()
    return JsonResponse(_state())


# --- the hub's keys -------------------------------------------------------------


def _hub_only() -> JsonResponse | None:
    if conf.mode() != "hub":
        return _refuse("Keys for other environments exist only while this install is the hub.")
    return None


@require_http_methods(["POST"])
@_guarded
def add_client(request: HttpRequest) -> JsonResponse:
    if refused := _hub_only():
        return refused
    data = _body(request)
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 100:
        return _refuse("Name the environment, up to 100 characters.")
    if HubClient.objects.filter(name__iexact=name).exists():
        return _refuse(f"There is already an environment called {name}.")
    row = HubClient(
        name=name, source=(str(data.get("source") or "").strip() or name)[:60],
        read_only=bool(data.get("readOnly")),
    )  # fmt: skip
    key = hub.issue(row)
    row.save()
    return JsonResponse({**_state(), "key": key, "keyFor": row.name})


def _client(pk: str) -> HubClient | None:
    return HubClient.objects.filter(pk=pk).first() if str(pk).isdigit() else None


@require_http_methods(["POST"])
@_guarded
def rotate_client(request: HttpRequest, pk: str) -> JsonResponse:
    if refused := _hub_only():
        return refused
    row = _client(pk)
    if row is None:
        return _refuse("No such environment.", 404)
    key = hub.issue(row)
    row.revoked_at = None
    row.save()
    return JsonResponse({**_state(), "key": key, "keyFor": row.name})


@require_http_methods(["POST"])
@_guarded
def update_client(request: HttpRequest, pk: str) -> JsonResponse:
    """Read-only on or off, or revoke (`revoke: true`) -- a revoked key stops at once."""
    if refused := _hub_only():
        return refused
    row = _client(pk)
    if row is None:
        return _refuse("No such environment.", 404)
    data = _body(request)
    if "readOnly" in data:
        row.read_only = bool(data["readOnly"])
    if data.get("revoke") and row.revoked_at is None:
        row.revoked_at = timezone.now()
    row.save()
    return JsonResponse(_state())

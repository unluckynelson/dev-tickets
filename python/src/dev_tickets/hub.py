"""The hub's API: other installs (clients) use this board over HTTP.

Only when `MODE = "hub"`; every path answers 404 otherwise. A client authenticates
with its key (`Authorization: Bearer dt_...`, made by `manage.py devtickets_client
add`) and says on each request who is acting:

    X-Dev-Tickets-Actor:   {"email": "...", "name": "...", "avatar": "...", "team": true}
    X-Dev-Tickets-Context: the client's CONTEXT_LABEL, UTF-8 percent-encoded

A valid key plus an actor is the whole access decision: the client has already
applied its own `CAN_ACCESS`, and the hub's applies only to the hub's own users.
The actor becomes a `Person`, matched by email, so someone who uses the board from
two environments is one person with one bell. Everything they do is stamped with
the client's `source`.

The schema and file views are the package's own; this module only sets the actor
(`actor.set_actor`) before handing the request on, so nothing downstream knows or
cares that the request came from another server.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from urllib.parse import unquote

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import GraphQLView

from . import conf, people, views
from .actor import Actor, set_actor
from .models import HubClient
from .schema import schema

KEY_PREFIX = "dt_"
ACTOR_HEADER = "X-Dev-Tickets-Actor"
CONTEXT_HEADER = "X-Dev-Tickets-Context"
# last_used_at is for "is this key still in use?", not an audit log.
TOUCH_EVERY = timedelta(minutes=1)

_graphql = GraphQLView.as_view(schema=schema)


class Refused(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


# --- keys ---------------------------------------------------------------------


def new_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def issue(client: HubClient) -> str:
    """Give `client` a fresh key, replacing any old one. Returns the key, which is
    not stored and cannot be shown again."""
    key = new_key()
    client.key_hash, client.key_prefix = hash_key(key), key[:8]
    return key


# --- authentication -----------------------------------------------------------


def authenticate(request: HttpRequest) -> HubClient:
    header = request.headers.get("Authorization", "")
    scheme, _, key = header.partition(" ")
    if scheme.lower() != "bearer" or not key.strip():
        raise Refused("A hub API key is required (Authorization: Bearer <key>).", 401)
    client = HubClient.objects.filter(key_hash=hash_key(key.strip())).first()
    if client is None or client.revoked_at is not None:
        raise Refused("That hub API key is not valid.", 401)
    now = timezone.now()
    if client.last_used_at is None or now - client.last_used_at >= TOUCH_EVERY:
        HubClient.objects.filter(pk=client.pk).update(last_used_at=now)
        client.last_used_at = now
    return client


def remote_actor(request: HttpRequest, client: HubClient) -> Actor:
    raw = request.headers.get(ACTOR_HEADER, "")
    if not raw:
        raise Refused(f"The {ACTOR_HEADER} header is required.", 400)
    try:
        data = json.loads(raw)
    except ValueError:
        raise Refused(f"The {ACTOR_HEADER} header must be JSON.", 400) from None
    if not isinstance(data, dict) or not people.normalise_email(data.get("email")):
        raise Refused(f"The {ACTOR_HEADER} header needs an email.", 400)
    person = people.for_remote(
        data.get("email"), name=data.get("name") or "", avatar=data.get("avatar") or "",
        team=data.get("team") is True,
    )  # fmt: skip
    context = unquote(request.headers.get(CONTEXT_HEADER, ""), errors="replace")[:150]
    return Actor(
        person=person, context_label=context, source=client.source, read_only=client.read_only
    )


def _api(view):
    """Hub mode only; authenticate, set the actor, then run `view`."""

    @csrf_exempt
    def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if conf.mode() != "hub":
            raise Http404
        try:
            client = authenticate(request)
            set_actor(request, remote_actor(request, client))
        except Refused as exc:
            return JsonResponse({"errors": [{"message": str(exc)}]}, status=exc.status)
        return view(request, *args, **kwargs)

    return wrapped


def _post_only(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"errors": [{"message": "POST only."}]}, status=405)
    return _graphql(request)


graphql = _api(_post_only)
upload = _api(views.upload)
attachment_file = _api(views.attachment_file)

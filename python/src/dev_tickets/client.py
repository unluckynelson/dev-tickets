"""Client mode: this install keeps no tickets and forwards its users to the hub.

The browser only ever talks to its own backend, at the same URLs as standalone, and
never sees the hub's address or key. For each request this module:

1. Decides locally whether the user may use dev tickets at all (`CAN_ACCESS`). Someone
   refused, signed out, or without an email address never reaches the hub: the
   package's own schema answers them (`devSupportConfig` says `enabled: false`,
   everything else is refused with the usual message).
2. Otherwise forwards the request with the key, an actor header (email, name, avatar,
   whether they are on the team) and the context label, and returns the hub's answer
   as it came.

If the hub cannot be reached, answers 5xx or takes longer than `HUB_TIMEOUT`, the
user gets "The ticket hub is unreachable" (HTTP 502) and the detail goes to the log.

Everything goes through `transport`, one function over the standard library's
urllib, so tests can route it into a hub in the same process.
"""

from __future__ import annotations

import json
import logging
import secrets
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import IO
from urllib.parse import quote

from django.core.exceptions import PermissionDenied
from django.http import (
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from strawberry.django.views import GraphQLView

from . import conf, people, service
from .actor import NO_ACCESS, SIGNED_OUT, Actor, set_actor
from .hub import ACTOR_HEADER, CONTEXT_HEADER
from .permissions import can_access, context_label
from .schema import schema

log = logging.getLogger(__name__)

UNREACHABLE = "The ticket hub is unreachable. Try again in a moment."
NO_EMAIL = "Your account needs an email address to use dev tickets."
API = "/devtickets/api/v1/"
CHUNK = 64 * 1024
# Response headers worth passing from the hub to the browser for a file.
FILE_HEADERS = ("Content-Type", "Content-Disposition", "Content-Length", "Cache-Control",
                "X-Content-Type-Options")  # fmt: skip

_local_graphql = GraphQLView.as_view(schema=schema)


class HubUnreachable(Exception):
    """The hub did not answer: refused, DNS, TLS, timeout."""


@dataclass
class HubResponse:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: IO[bytes] | None = None

    def read(self) -> bytes:
        return self.body.read() if self.body is not None else b""

    def chunks(self) -> Iterator[bytes]:
        if self.body is None:
            return
        try:
            while chunk := self.body.read(CHUNK):
                yield chunk
        finally:
            self.body.close()

    def close(self) -> None:
        if self.body is not None:
            self.body.close()


def transport(
    method: str, url: str, *, headers: dict[str, str], body: bytes | None = None,
    timeout: float = 10,
) -> HubResponse:  # fmt: skip
    """One HTTP request to the hub. An HTTP error status is returned, not raised;
    only a hub that does not answer raises `HubUnreachable`."""
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=timeout)  # noqa: S310 -- configured URL
    except urllib.error.HTTPError as exc:
        return HubResponse(exc.code, dict(exc.headers.items()), exc)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise HubUnreachable(str(getattr(exc, "reason", exc))) from exc
    return HubResponse(response.status, dict(response.headers.items()), response)


# --- who ----------------------------------------------------------------------


def _refusal(user) -> str:
    """Why this user is handled here and not forwarded; "" when they may go on."""
    if user is None or not getattr(user, "is_authenticated", False):
        return SIGNED_OUT
    if not can_access(user):
        return NO_ACCESS
    if not people.normalise_email(getattr(user, "email", "")):
        return NO_EMAIL
    return ""


def _actor_header(user) -> str:
    avatar_hook = conf.hook("AVATAR")
    team = conf.hook("TEAM")().filter(is_active=True, pk=user.pk).exists()
    return json.dumps({
        "email": people.normalise_email(user.email),
        "name": people.user_name(user),
        "avatar": str(avatar_hook(user) or "") if avatar_hook else "",
        "team": team,
    })  # fmt: skip


def _headers(request: HttpRequest, **extra: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {conf.get('HUB_API_KEY')}",
        ACTOR_HEADER: _actor_header(request.user),
        CONTEXT_HEADER: quote(context_label(request), safe=""),
        "Accept": "application/json",
        **extra,
    }


def _call(request: HttpRequest, method: str, path: str, **kwargs) -> HubResponse:
    url = str(conf.get("HUB_URL")).rstrip("/") + API + path
    response = transport(
        method, url, headers=_headers(request, **kwargs.pop("headers", {})),
        timeout=float(conf.get("HUB_TIMEOUT")), **kwargs,
    )  # fmt: skip
    if response.status >= 500:
        detail = response.read()[:500]
        response.close()
        raise HubUnreachable(f"HTTP {response.status} from the hub: {detail!r}")
    return response


# --- views --------------------------------------------------------------------


def graphql(request: HttpRequest) -> HttpResponse:
    """`devtickets/graphql/` in client mode."""
    refusal = _refusal(request.user)
    if refusal or request.method != "POST":
        # Answered here, by the package's own resolvers, with the reason as refusal.
        set_actor(request, Actor(refusal=refusal or NO_ACCESS))
        return _local_graphql(request)
    try:
        response = _call(
            request, "POST", "graphql/", body=request.body,
            headers={"Content-Type": "application/json"},
        )  # fmt: skip
    except HubUnreachable as exc:
        log.warning("Dev tickets: hub request failed: %s", exc)
        return JsonResponse({"data": None, "errors": [{"message": UNREACHABLE}]}, status=502)
    body = response.read()
    response.close()
    return HttpResponse(
        body, status=response.status,
        content_type=response.headers.get("Content-Type", "application/json"),
    )  # fmt: skip


def _problem(message: str, status: int) -> JsonResponse:
    return JsonResponse({"problems": [message]}, status=status)


def upload(request: HttpRequest, ref: str) -> HttpResponse:
    """`devtickets-files/<ref>/` in client mode: checked here, then sent on."""
    if request.method != "POST":
        return HttpResponse(status=405)
    refusal = _refusal(request.user)
    if refusal:
        return _problem(refusal, 403)
    files = request.FILES.getlist("file")
    if not files:
        return _problem("Choose a file to upload.", 400)
    try:
        for f in files:
            service.check_upload_size(f)
    except PermissionDenied as exc:
        return _problem(str(exc), 400)
    body, content_type = _multipart(files)
    try:
        response = _call(
            request, "POST", f"files/{quote(ref, safe='')}/", body=body,
            headers={"Content-Type": content_type},
        )  # fmt: skip
    except HubUnreachable as exc:
        log.warning("Dev tickets: hub upload failed: %s", exc)
        return _problem(UNREACHABLE, 502)
    answer = response.read()
    response.close()
    return HttpResponse(
        answer, status=response.status,
        content_type=response.headers.get("Content-Type", "application/json"),
    )  # fmt: skip


def attachment_file(request: HttpRequest, attachment_id: int) -> HttpResponse:
    """`devtickets-files/attachment/<id>/` in client mode: streamed from the hub."""
    if request.method != "GET":
        return HttpResponse(status=405)
    if _refusal(request.user):
        raise PermissionDenied
    query = "?download=1" if request.GET.get("download") == "1" else ""
    try:
        response = _call(request, "GET", f"files/attachment/{int(attachment_id)}/{query}")
    except HubUnreachable as exc:
        log.warning("Dev tickets: hub download failed: %s", exc)
        return HttpResponse(UNREACHABLE, status=502, content_type="text/plain")
    if response.status != 200:
        body = response.read()
        response.close()
        return HttpResponse(
            body, status=response.status,
            content_type=response.headers.get("Content-Type", "text/plain"),
        )  # fmt: skip
    streamed = StreamingHttpResponse(response.chunks(), status=200)
    for name in FILE_HEADERS:
        value = _header(response.headers, name)
        if value:
            streamed[name] = value
    return streamed


def _header(headers: Mapping[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""


def _multipart(files) -> tuple[bytes, str]:
    """`files` as a multipart/form-data body, each under the field name `file`."""
    boundary = "devtickets-" + secrets.token_hex(16)
    parts: list[bytes] = []
    for f in files:
        name = (f.name or "file").replace('"', "").replace("\r", "").replace("\n", "")
        kind = f.content_type or "application/octet-stream"
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{name}\"\r\nContent-Type: {kind}\r\n\r\n".encode()
        )
        f.seek(0)
        parts.append(f.read())
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"

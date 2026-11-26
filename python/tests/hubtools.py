"""Helpers for the hub and client tests: a hub client with a key, the API's headers,
and a transport that routes a client's requests into the hub in this process."""

from __future__ import annotations

import io
import json
from urllib.parse import urlsplit

from django.conf import settings
from django.test import Client, override_settings

from dev_tickets import hub
from dev_tickets.client import HubResponse, HubUnreachable
from dev_tickets.models import HubClient

API = "/devtickets/api/v1/"


def make_client(name="staging", source="staging", read_only=False) -> tuple[HubClient, str]:
    row = HubClient(name=name, source=source, read_only=read_only)
    key = hub.issue(row)
    row.save()
    return row, key


def actor(email="priya@example.com", name="Priya Shah", team=False, **more) -> str:
    return json.dumps({"email": email, "name": name, "avatar": "", "team": team, **more})


def api_headers(key: str | None, who: str | None = None, context: str = "") -> dict:
    headers = {}
    if key is not None:
        headers["Authorization"] = f"Bearer {key}"
    if who is not None:
        headers[hub.ACTOR_HEADER] = who
    if context:
        headers[hub.CONTEXT_HEADER] = context
    return headers


def api_gql(key, query, variables=None, who=None, context="", status=200) -> dict:
    """A GraphQL request to the hub's API, as a client server makes it."""
    with override_settings(DEV_TICKETS={**settings.DEV_TICKETS, "MODE": "hub"}):
        response = Client().post(
            API + "graphql/", data=json.dumps({"query": query, "variables": variables or {}}),
            content_type="application/json", headers=api_headers(key, who, context),
        )  # fmt: skip
    assert response.status_code == status, response.content
    return response.json()


class Router:
    """Stands in for `dev_tickets.client.transport`: runs each request against the
    hub view in this process, with MODE switched to "hub" for the call."""

    def __init__(self, down=False, status=None):
        self.calls: list[dict] = []
        self.down = down
        self.status = status

    def __call__(self, method, url, *, headers, body=None, timeout=10):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        if self.down:
            raise HubUnreachable("connection refused")
        if self.status:
            return HubResponse(self.status, {"Content-Type": "text/html"},
                               io.BytesIO(b"<h1>Bad gateway</h1>"))  # fmt: skip
        parts = urlsplit(url)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        extra = {k: v for k, v in headers.items() if k.lower() != "content-type"}
        with override_settings(DEV_TICKETS={**settings.DEV_TICKETS, "MODE": "hub"}):
            response = Client().generic(
                method, path, data=body or b"",
                content_type=headers.get("Content-Type", "application/octet-stream"),
                headers=extra,
            )  # fmt: skip
            content = (
                b"".join(response.streaming_content) if response.streaming else response.content
            )
            response.close()
        return HubResponse(response.status_code, dict(response.items()), io.BytesIO(content))

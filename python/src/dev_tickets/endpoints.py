"""The browser-facing endpoints, which serve this database or forward to the hub
depending on `MODE`, decided per request so tests can switch modes."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from strawberry.django.views import GraphQLView

from . import client, conf, views
from .schema import schema

_graphql = GraphQLView.as_view(schema=schema)


def graphql(request: HttpRequest) -> HttpResponse:
    if conf.mode() == "client":
        return client.graphql(request)
    return _graphql(request)


@require_POST
def upload(request: HttpRequest, ref: str) -> HttpResponse:
    if conf.mode() == "client":
        return client.upload(request, ref)
    return views.upload(request, ref)


@require_GET
def attachment_file(request: HttpRequest, attachment_id: int) -> HttpResponse:
    if conf.mode() == "client":
        return client.attachment_file(request, attachment_id)
    return views.attachment_file(request, attachment_id)

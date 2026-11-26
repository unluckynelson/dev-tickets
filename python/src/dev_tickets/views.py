"""Ticket attachments over plain HTTP: multipart upload, and serving the bytes.

Gated like everything else (`actor.require`): a screenshot shows whatever the
reporter had open, which may be someone else's data. The hub API (`hub.py`) serves
these same views once it has set the actor from the client's key.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from . import service
from .actor import require
from .models import TicketAttachment

# Shown inline only if one of these; anything else downloads. An uploaded HTML or SVG
# opened inline on the app's origin could run script with the viewer's session.
INLINE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}


def csrf(request: HttpRequest) -> HttpResponse:
    """`GET devtickets/csrf/`: sets the CSRF cookie a host frontend needs before its
    first POST. GraphQL sends reads over POST too, so even a query needs it."""
    return HttpResponse(status=204)


@require_POST
def upload(request: HttpRequest, ref: str) -> JsonResponse:
    """`POST /devtickets-files/<DEV-12>/` with multipart `file` (one or more)."""
    try:
        actor = require(request, write=True)
    except PermissionDenied as exc:
        return JsonResponse({"problems": [str(exc)]}, status=403)
    ticket = service.find_ticket(ref)
    if ticket is None:
        return JsonResponse({"problems": [f"No ticket {ref}."]}, status=404)
    files = request.FILES.getlist("file")
    if not files:
        return JsonResponse({"problems": ["Choose a file to upload."]}, status=400)
    try:
        made = [service.add_attachment(ticket, actor, f) for f in files]
    except PermissionDenied as exc:
        return JsonResponse({"problems": [str(exc)]}, status=400)
    return JsonResponse({"problems": [], "ids": [str(a.pk) for a in made]}, status=201)


@require_GET
def attachment_file(request: HttpRequest, attachment_id: int) -> FileResponse:
    """`GET /devtickets-files/attachment/<id>/` (`?download=1` to save it)."""
    require(request)
    attachment = TicketAttachment.objects.filter(pk=attachment_id).first()
    if attachment is None or not attachment.file:
        raise Http404
    inline = attachment.content_type in INLINE_TYPES and request.GET.get("download") != "1"
    response = FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type if inline else "application/octet-stream",
        as_attachment=not inline,
        filename=attachment.name,
    )
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response

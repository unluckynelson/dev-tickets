"""GraphQL shapes for dev tickets, and the functions that build them from rows.

A ticket's GraphQL `id` is its identifier ("DEV-12"): it is what the route carries,
what people paste, and what `service.find_ticket` reads, so there is one handle.
"""

from __future__ import annotations

import datetime as dt

import strawberry

from . import notify, states
from .models import DevTicket, TicketComment, TicketRelation
from .service import display_name


@strawberry.type
class TicketMemberType:
    id: str
    name: str
    email: str


@strawberry.type
class TicketPriorityType:
    value: int
    label: str


@strawberry.type
class TicketStateType:
    id: str
    name: str
    type: str
    on_board: bool
    # Filled by `devTicketLanes` only (the Settings dialog); 0 elsewhere.
    tickets: int = 0


def state_type_of(lane, tickets: int = 0) -> TicketStateType:
    return TicketStateType(
        id=lane.key, name=lane.name, type=lane.type, on_board=lane.on_board, tickets=tickets
    )


@strawberry.type
class TicketLabelType:
    id: str
    name: str
    color: str


@strawberry.type
class DevSupportConfigType:
    """Everything the widget, board and dialog need before anyone types."""

    # False for anyone signed out or outside the team: the widget and bell hide.
    enabled: bool
    prefix: str
    board_url: str
    team_name: str
    states: list[TicketStateType]
    labels: list[TicketLabelType]
    assignees: list[TicketMemberType]
    default_assignee_id: str | None
    priorities: list[TicketPriorityType]
    email_updates: bool


@strawberry.type
class BoardIssueType:
    id: str
    identifier: str
    title: str
    priority: int
    state_id: str
    state_name: str
    state_type: str
    assignee_id: str
    assignee_name: str
    reporter_id: str
    reporter_name: str
    context_label: str
    # The hub client it was filed through ("staging"); "" when filed here.
    source: str
    labels: list[TicketLabelType]
    comment_count: int
    cover_id: str | None  # the first image attachment, shown on the card
    created_at: dt.datetime
    updated_at: dt.datetime


@strawberry.type
class BoardLaneType:
    id: str
    name: str
    type: str
    issues: list[BoardIssueType]


@strawberry.type
class BoardType:
    team_name: str
    lanes: list[BoardLaneType]


@strawberry.type
class IssueCommentType:
    id: str
    body: str
    author_id: str
    author_name: str
    created_at: dt.datetime
    edited_at: dt.datetime | None
    mine: bool
    source: str


@strawberry.type
class TicketEventType:
    id: str
    kind: str
    actor_name: str
    summary: str
    created_at: dt.datetime


@strawberry.type
class TicketRefType:
    id: str
    identifier: str
    title: str
    state_name: str
    state_type: str


@strawberry.type
class TicketRelationType:
    id: str
    kind: str
    # As read from the ticket being shown: "Blocks" one way is "Blocked by" the other.
    label: str
    ticket: TicketRefType


@strawberry.type
class TicketAttachmentType:
    id: str
    name: str
    content_type: str
    size: int
    uploader_name: str
    created_at: dt.datetime


@strawberry.type
class IssueDetailType:
    id: str
    identifier: str
    title: str
    description: str
    priority: int
    state_id: str
    state_name: str
    state_type: str
    assignee_id: str
    assignee_name: str
    reporter_id: str
    reporter_name: str
    page_url: str
    context_label: str
    source: str
    labels: list[TicketLabelType]
    comments: list[IssueCommentType]
    events: list[TicketEventType]
    relations: list[TicketRelationType]
    attachments: list[TicketAttachmentType]
    subscriber_names: list[str]
    subscribed: bool
    created_at: dt.datetime
    updated_at: dt.datetime


@strawberry.type
class TicketNotificationType:
    id: str
    read: bool
    summary: str
    created_at: dt.datetime
    ticket: TicketRefType


@strawberry.type
class DevTicketFeedType:
    notifications: list[TicketNotificationType]
    unread_count: int
    email_updates: bool


# --- builders -----------------------------------------------------------------


def label_type(label) -> TicketLabelType:
    return TicketLabelType(id=str(label.pk), name=label.name, color=label.color)


def member_type(person) -> TicketMemberType:
    return TicketMemberType(
        id=str(person.pk), name=display_name(person), email=person.email or ""
    )


def ticket_ref(ticket: DevTicket) -> TicketRefType:
    return TicketRefType(
        id=ticket.identifier, identifier=ticket.identifier, title=ticket.title,
        state_name=ticket.state_name, state_type=ticket.state_type,
    )  # fmt: skip


def card_queryset():
    from django.db.models import Count, OuterRef, Subquery

    from .models import TicketAttachment

    first_image = TicketAttachment.objects.filter(
        ticket=OuterRef("pk"), content_type__startswith="image/"
    ).order_by("created_at", "pk")
    return (
        DevTicket.objects.select_related("assignee", "reported_by")
        .prefetch_related("labels")
        .annotate(
            n_comments=Count("comments", distinct=True),
            cover=Subquery(first_image.values("pk")[:1]),
        )
    )


def issue_card(ticket: DevTicket) -> BoardIssueType:
    count = getattr(ticket, "n_comments", None)
    if count is None:
        count = ticket.comments.count()
    return BoardIssueType(
        id=ticket.identifier,
        identifier=ticket.identifier,
        title=ticket.title,
        priority=ticket.priority,
        state_id=ticket.state,
        state_name=ticket.state_name,
        state_type=ticket.state_type,
        assignee_id=str(ticket.assignee_id or ""),
        assignee_name=display_name(ticket.assignee),
        reporter_id=str(ticket.reported_by_id or ""),
        reporter_name=display_name(ticket.reported_by),
        context_label=ticket.context_label,
        source=ticket.source,
        labels=[label_type(lbl) for lbl in ticket.labels.all()],
        comment_count=count,
        cover_id=str(ticket.cover) if getattr(ticket, "cover", None) else None,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def card_for(ticket: DevTicket) -> BoardIssueType:
    """A fresh card for one ticket, after a change."""
    return issue_card(card_queryset().get(pk=ticket.pk))


def comment_type(comment: TicketComment, viewer) -> IssueCommentType:
    """`viewer` is the reading Person: `mine` is whether they wrote it."""
    return IssueCommentType(
        id=str(comment.pk),
        body=comment.body,
        author_id=str(comment.author_id or ""),
        author_name=display_name(comment.author) or "Unknown",
        created_at=comment.created_at,
        edited_at=comment.edited_at,
        mine=comment.author_id is not None and comment.author_id == viewer.pk,
        source=comment.source,
    )


_OUT_LABEL = {
    states.RELATED: "Related to",
    states.BLOCKS: "Blocks",
    states.DUPLICATE_OF: "Duplicate of",
}
_IN_LABEL = {
    states.RELATED: "Related to",
    states.BLOCKS: "Blocked by",
    states.DUPLICATE_OF: "Duplicated by",
}


def _relations(ticket: DevTicket) -> list[TicketRelationType]:
    rows: list[TicketRelationType] = []
    out = TicketRelation.objects.filter(ticket=ticket).select_related("other")
    for r in out:
        rows.append(TicketRelationType(
            id=str(r.pk), kind=r.kind, label=_OUT_LABEL[r.kind], ticket=ticket_ref(r.other)
        ))  # fmt: skip
    into = TicketRelation.objects.filter(other=ticket).select_related("ticket")
    for r in into:
        rows.append(TicketRelationType(
            id=str(r.pk), kind=r.kind, label=_IN_LABEL[r.kind], ticket=ticket_ref(r.ticket)
        ))  # fmt: skip
    return sorted(rows, key=lambda r: (r.label, r.ticket.identifier))


def issue_detail(ticket: DevTicket, viewer) -> IssueDetailType:
    ticket = DevTicket.objects.select_related("assignee", "reported_by").get(pk=ticket.pk)
    comments = ticket.comments.select_related("author")
    events = ticket.events.select_related("actor").exclude(kind="comment")
    subscribers = [s.person for s in ticket.subscriptions.select_related("person")]
    return IssueDetailType(
        id=ticket.identifier,
        identifier=ticket.identifier,
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        state_id=ticket.state,
        state_name=ticket.state_name,
        state_type=ticket.state_type,
        assignee_id=str(ticket.assignee_id or ""),
        assignee_name=display_name(ticket.assignee),
        reporter_id=str(ticket.reported_by_id or ""),
        reporter_name=display_name(ticket.reported_by),
        page_url=ticket.page_url,
        context_label=ticket.context_label,
        source=ticket.source,
        labels=[label_type(lbl) for lbl in ticket.labels.all()],
        comments=[comment_type(c, viewer) for c in comments],
        events=[
            TicketEventType(
                id=str(e.pk),
                kind=e.kind,
                actor_name=display_name(e.actor) or "Someone",
                summary=notify.summary(e),
                created_at=e.created_at,
            )  # fmt: skip
            for e in events
        ],
        relations=_relations(ticket),
        attachments=[
            TicketAttachmentType(
                id=str(a.pk),
                name=a.name,
                content_type=a.content_type,
                size=a.size,
                uploader_name=display_name(a.uploaded_by),
                created_at=a.created_at,
            )  # fmt: skip
            for a in ticket.attachments.select_related("uploaded_by")
        ],
        subscriber_names=sorted(display_name(u) for u in subscribers),
        subscribed=any(p.pk == viewer.pk for p in subscribers),
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )

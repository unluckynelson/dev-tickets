"""Read resolvers. Every one checks `CAN_ACCESS`, except the config query, which
answers `enabled: false` instead so a host layout can ask without guarding."""

from __future__ import annotations

import strawberry
from django.db.models import Q

from . import conf, service, states
from .digest import board_url
from .models import DevTicket, TicketLabel, TicketNotification
from .notify import summary
from .permissions import access_required, can_access
from .types import (
    BoardLaneType,
    BoardType,
    DevSupportConfigType,
    DevTicketFeedType,
    IssueDetailType,
    TicketNotificationType,
    TicketPriorityType,
    TicketRefType,
    TicketStateType,
    card_queryset,
    issue_card,
    issue_detail,
    label_type,
    member_type,
    ticket_ref,
)


def _user(info: strawberry.Info):
    return info.context.request.user


def dev_support_config(info: strawberry.Info) -> DevSupportConfigType:
    user = _user(info)
    common = {
        "prefix": states.prefix(),
        "board_url": board_url(),
        "team_name": str(conf.get("TEAM_NAME")),
        "states": [
            TicketStateType(id=s.key, name=s.name, type=s.type, on_board=s.on_board)
            for s in states.STATES
        ],
        "priorities": [TicketPriorityType(value=v, label=lbl) for v, lbl in states.PRIORITIES],
    }
    if not can_access(user):
        return DevSupportConfigType(
            enabled=False, labels=[], assignees=[], default_assignee_id=None,
            email_updates=False, **common,
        )  # fmt: skip
    default = service.default_assignee()
    return DevSupportConfigType(
        enabled=True,
        labels=[label_type(lbl) for lbl in TicketLabel.objects.all()],
        assignees=[member_type(u) for u in service.team_members()],
        default_assignee_id=str(default.pk) if default else None,
        email_updates=service.prefs_for(user).email_updates,
        **common,
    )


def dev_ticket_board(info: strawberry.Info) -> BoardType:
    """Every ticket in an on-board state, lane by lane, newest arrival on top.
    Canceled and duplicate tickets are off the board."""
    access_required(_user(info))
    on_board = [s for s in states.STATES if s.on_board]
    tickets = (
        card_queryset()
        .filter(state__in=[s.key for s in on_board])
        .order_by("-state_changed_at", "-number")
    )
    by_state: dict[str, list] = {s.key: [] for s in on_board}
    for ticket in tickets:
        by_state[ticket.state].append(issue_card(ticket))
    return BoardType(
        team_name=str(conf.get("TEAM_NAME")),
        lanes=[
            BoardLaneType(id=s.key, name=s.name, type=s.type, issues=by_state[s.key])
            for s in on_board
        ],
    )


def dev_ticket_detail(info: strawberry.Info, id: str) -> IssueDetailType | None:
    user = access_required(_user(info))
    ticket = service.find_ticket(id)
    return issue_detail(ticket, user) if ticket else None


def dev_ticket_search(info: strawberry.Info, query: str, limit: int = 10) -> list[TicketRefType]:
    """Tickets by identifier or title words, closed ones included -- for linking."""
    access_required(_user(info))
    rows = DevTicket.objects.all()
    number = states.parse_identifier(query)
    if number is not None:
        rows = rows.filter(number=number)
    else:
        for word in query.split():
            rows = rows.filter(Q(title__icontains=word) | Q(description__icontains=word))
    return [ticket_ref(t) for t in rows.order_by("-number")[: max(1, min(limit, 50))]]


def dev_tickets(info: strawberry.Info, limit: int = 30) -> DevTicketFeedType:
    """The bell: what happened on tickets you follow, by someone else, newest first."""
    user = access_required(_user(info))
    rows = (
        TicketNotification.objects.filter(user=user)
        .select_related("event__ticket", "event__actor")
        .order_by("-created_at", "-pk")[: max(1, min(limit, 100))]
    )
    return DevTicketFeedType(
        notifications=[
            TicketNotificationType(
                id=str(n.pk),
                read=n.read_at is not None,
                summary=summary(n.event),
                created_at=n.created_at,
                ticket=ticket_ref(n.event.ticket),
            )  # fmt: skip
            for n in rows
        ],
        unread_count=TicketNotification.objects.filter(user=user, read_at__isnull=True).count(),
        email_updates=service.prefs_for(user).email_updates,
    )


@strawberry.type
class Query:
    dev_support_config: DevSupportConfigType = strawberry.field(resolver=dev_support_config)
    dev_tickets: DevTicketFeedType = strawberry.field(resolver=dev_tickets)
    dev_ticket_board: BoardType = strawberry.field(resolver=dev_ticket_board)
    dev_ticket_detail: IssueDetailType | None = strawberry.field(resolver=dev_ticket_detail)
    dev_ticket_search: list[TicketRefType] = strawberry.field(resolver=dev_ticket_search)

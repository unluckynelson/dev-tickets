"""Read resolvers. Every one asks for the request's actor (`actor.require`), except
the config query, which answers `enabled: false` instead so a host layout can ask
without guarding."""

from __future__ import annotations

import strawberry
from django.db.models import Count, Q

from . import conf, service, states
from .actor import actor_for, require
from .digest import board_url
from .models import DevTicket, TicketLabel, TicketNotification, TicketState
from .notify import summary
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
    state_type_of,
    ticket_ref,
)


def _person(info: strawberry.Info):
    return require(info.context.request).person


def dev_support_config(info: strawberry.Info) -> DevSupportConfigType:
    actor = actor_for(info.context.request)
    common = {
        "prefix": states.prefix(),
        "board_url": board_url(),
        "team_name": str(conf.get("TEAM_NAME")),
        "states": [
            TicketStateType(id=s.key, name=s.name, type=s.type, on_board=s.on_board)
            for s in states.all_states()
        ],
        "priorities": [TicketPriorityType(value=v, label=lbl) for v, lbl in states.PRIORITIES],
    }
    if actor.person is None:
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
        email_updates=service.prefs_for(actor.person).email_updates,
        **common,
    )


def dev_ticket_lanes(info: strawberry.Info) -> list[TicketStateType]:
    """Every lane in order, with how many tickets each holds (the Settings dialog)."""
    _person(info)
    counts = dict(
        DevTicket.objects.values_list("state").annotate(n=Count("pk")).values_list("state", "n")
    )
    return [state_type_of(lane, counts.get(lane.key, 0)) for lane in TicketState.objects.all()]


def dev_ticket_board(info: strawberry.Info) -> BoardType:
    """Every ticket in an on-board state, lane by lane, newest arrival on top.
    Canceled and duplicate tickets are off the board."""
    _person(info)
    on_board = states.board_states()
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
    person = _person(info)
    ticket = service.find_ticket(id)
    return issue_detail(ticket, person) if ticket else None


def dev_ticket_search(info: strawberry.Info, query: str, limit: int = 10) -> list[TicketRefType]:
    """Tickets by identifier or title words, closed ones included -- for linking."""
    _person(info)
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
    person = _person(info)
    rows = (
        TicketNotification.objects.filter(person=person)
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
        unread_count=TicketNotification.objects.filter(person=person, read_at__isnull=True).count(),
        email_updates=service.prefs_for(person).email_updates,
    )


@strawberry.type
class Query:
    dev_support_config: DevSupportConfigType = strawberry.field(resolver=dev_support_config)
    dev_tickets: DevTicketFeedType = strawberry.field(resolver=dev_tickets)
    dev_ticket_board: BoardType = strawberry.field(resolver=dev_ticket_board)
    dev_ticket_detail: IssueDetailType | None = strawberry.field(resolver=dev_ticket_detail)
    dev_ticket_search: list[TicketRefType] = strawberry.field(resolver=dev_ticket_search)
    dev_ticket_lanes: list[TicketStateType] = strawberry.field(resolver=dev_ticket_lanes)

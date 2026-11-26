"""Ticket tools for an AI assistant, as plain definitions any MCP server can register.

Each tool is a name, a description, a JSON-schema for its arguments and a handler
`handler(user, **arguments) -> dict`. The handler checks `CAN_ACCESS` itself and
every write goes through `service`, as the GraphQL mutations do, so a change made by
an assistant is validated, logged and notified exactly like one made by a person.

A refusal raises `service.TicketError` (a `PermissionDenied`) with a message worded
for the model; a host should return it to the model as a tool error.

    from dev_tickets.mcp import register_tools

    register_tools(lambda name, description, schema, handler: server.add_tool(...))
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db.models import Q

from . import service, states
from .models import DevTicket, TicketLabel, TicketRelation
from .notify import summary
from .permissions import access_required
from .service import KEEP, TicketError, display_name

INSTRUCTIONS = """\
A product team's issue tracker. A ticket is <PREFIX>-<n>; pass that identifier wherever
a tool asks for a ticket.

States: triage (new, not yet looked at), backlog, todo, in_progress, done, and the
off-board closures canceled and duplicate. Priority: 1 urgent, 2 high, 3 medium,
4 low, 0 none. tickets_team lists who can hold a ticket and the labels in use.

Every ticket has a reporter, and the people subscribed to it (reporter, assignee,
commenters) are told about every change. So: do not move, reassign or comment on a
ticket the user did not ask about, and say what you changed. Before filing, search
with tickets_list to avoid a duplicate; if one exists, comment on it or link the two
instead. When you finish work on a ticket, move it to done and comment with what
changed."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., dict]
    read_only: bool = True


# --- JSON-schema helpers ------------------------------------------------------


def _string(description: str) -> dict:
    return {"type": "string", "description": description}


def _integer(description: str, minimum: int, maximum: int) -> dict:
    return {"type": "integer", "description": description, "minimum": minimum, "maximum": maximum}


def _enum(description: str, values: list[str]) -> dict:
    return {"type": "string", "description": description, "enum": values}


def _schema(properties: dict, required: tuple[str, ...] = ()) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


KINDS = list(states.RELATION_KINDS)
TICKET = _string("The ticket, e.g. DEV-12.")
LABELS = {"type": "array", "description": "Label names.", "items": _string("A label name.")}


# --- shapes the model reads ---------------------------------------------------


def ticket_brief(t: DevTicket) -> dict:
    return {
        "ticket": t.identifier,
        "title": t.title,
        "state": t.state,
        "priority": states.PRIORITY_LABELS.get(t.priority, ""),
        "assignee": display_name(t.assignee) or None,
        "reporter": display_name(t.reported_by) or None,
        "labels": [lbl.name for lbl in t.labels.all()],
        "created": t.created_at.date().isoformat(),
        "updated": t.updated_at.isoformat(),
    }


def ticket_detail(t: DevTicket) -> dict:
    t = DevTicket.objects.select_related("assignee", "reported_by").get(pk=t.pk)
    links = [
        {"kind": r.kind, "direction": "out", "ticket": r.other.identifier, "title": r.other.title}
        for r in TicketRelation.objects.filter(ticket=t).select_related("other")
    ] + [
        {"kind": r.kind, "direction": "in", "ticket": r.ticket.identifier, "title": r.ticket.title}
        for r in TicketRelation.objects.filter(other=t).select_related("ticket")
    ]
    return {
        **ticket_brief(t),
        "description": t.description,
        "page_url": t.page_url or None,
        "filed_from": t.context_label or None,
        "comments": [
            {"author": display_name(c.author), "at": c.created_at.isoformat(), "body": c.body}
            for c in t.comments.select_related("author")
        ],
        "history": [
            {"at": e.created_at.isoformat(), "what": summary(e)}
            for e in t.events.select_related("actor").exclude(kind="comment")
        ],
        "links": links,
        "followers": sorted(
            display_name(s.person) for s in t.subscriptions.select_related("person")
        ),
        "attachments": [a.name for a in t.attachments.all()],
    }


# --- argument helpers ---------------------------------------------------------


def _as_int(value, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise TicketError(f"{name} must be a whole number.") from None


def _person(text):
    if text in (None, ""):
        return None
    found = service.find_member(str(text))
    if found is None:
        raise TicketError(f"No single team member matches {text!r}; see tickets_team.")
    return found


def _labels(names):
    if names is None:
        return KEEP
    if not isinstance(names, list):
        raise TicketError("labels must be a list of label names.")
    by_name = {lbl.name.lower(): lbl for lbl in TicketLabel.objects.all()}
    missing = [n for n in names if str(n).lower() not in by_name]
    if missing:
        raise TicketError(f"Unknown label(s): {', '.join(map(str, missing))}; see tickets_team.")
    return [by_name[str(n).lower()] for n in names]


# --- handlers -----------------------------------------------------------------


def team(user) -> dict:
    access_required(user)
    return {
        "members": [
            {"id": str(u.pk), "name": display_name(u), "email": getattr(u, "email", "")}
            for u in service.team_members()
        ],
        "states": [
            {"key": s.key, "name": s.name, "on_board": s.on_board} for s in states.all_states()
        ],
        "priorities": [{"value": v, "label": lbl} for v, lbl in states.PRIORITIES],
        "labels": [lbl.name for lbl in TicketLabel.objects.all()],
        "prefix": states.prefix(),
    }


def list_tickets(
    user, search="", state=None, assignee=None, reporter=None, label=None,
    include_closed=False, limit=25,
) -> dict:  # fmt: skip
    access_required(user)
    rows = DevTicket.objects.select_related("assignee", "reported_by").prefetch_related("labels")
    number = states.parse_identifier(search or "")
    if number is not None:
        rows = rows.filter(number=number)
    else:
        for word in str(search or "").split():
            rows = rows.filter(Q(title__icontains=word) | Q(description__icontains=word))
    if state:
        rows = rows.filter(state=state)
    elif not include_closed:
        rows = rows.exclude(state__in=states.closed_keys())
    if assignee:
        rows = (
            rows.filter(assignee__isnull=True)
            if str(assignee).lower() == "none"
            else rows.filter(assignee=_person(assignee))
        )
    if reporter:
        rows = rows.filter(reported_by=_person(reporter))
    if label:
        rows = rows.filter(labels__name__iexact=label)
    limit = max(1, min(_as_int(limit, "limit"), 100))
    found = list(rows.order_by("-number")[:limit])
    return {"count": len(found), "tickets": [ticket_brief(t) for t in found]}


def get_ticket(user, ticket) -> dict:
    access_required(user)
    return ticket_detail(service.ticket_or_refuse(ticket))


def create(
    user, title, description="", priority=3, assignee=None, labels=None, state=None
) -> dict:
    access_required(user)
    ticket = service.create_ticket(
        user=user, title=title, description=description, priority=_as_int(priority, "priority"),
        assignee=_person(assignee), labels=_labels(labels or []), state=state,
    )  # fmt: skip
    return ticket_detail(ticket)


def update(
    user, ticket, title=None, description=None, priority=None, state=None, assignee=None,
    labels=None,
) -> dict:  # fmt: skip
    access_required(user)
    if assignee is None:
        person = KEEP
    elif str(assignee).lower() == "none":
        person = None
    else:
        person = _person(assignee)
    row = service.update_ticket(
        service.ticket_or_refuse(ticket), user,
        title=KEEP if title is None else title,
        description=KEEP if description is None else description,
        priority=KEEP if priority is None else _as_int(priority, "priority"),
        state=KEEP if state is None else state,
        assignee=person, labels=_labels(labels),
    )  # fmt: skip
    return ticket_detail(row)


def comment(user, ticket, body) -> dict:
    access_required(user)
    row = service.ticket_or_refuse(ticket)
    service.add_comment(row, user, body)
    return ticket_detail(row)


def link(user, ticket, other, kind) -> dict:
    access_required(user)
    row = service.ticket_or_refuse(ticket)
    service.add_relation(row, user, service.ticket_or_refuse(other), kind)
    return ticket_detail(row)


def unlink(user, ticket, other) -> dict:
    access_required(user)
    row, that = service.ticket_or_refuse(ticket), service.ticket_or_refuse(other)
    links = row.relations_out.filter(other=that) | row.relations_in.filter(ticket=that)
    if not links.exists():
        raise TicketError(f"{row.identifier} and {that.identifier} are not linked.")
    for relation in list(links):
        service.remove_relation(relation.pk, user)
    return ticket_detail(row)


TOOLS: tuple[Tool, ...] = (
    Tool(
        "team",
        "Who can hold a ticket, the states, priorities and labels.",
        _schema({}),
        team,
    ),
    Tool(
        "list",
        "Tickets, newest first, filtered by any of: words in the title or description, "
        "state, assignee, reporter, label. Closed tickets (done, canceled, duplicate) "
        "only when include_closed is true or a closed state is asked for.",
        _schema({
            "search": _string("Words to find in the title or description, or <PREFIX>-<n>."),
            "state": _string("Only this lane: a state key from team."),
            "assignee": _string("Name, email or 'none' for unassigned."),
            "reporter": _string("Name or email of who raised it."),
            "label": _string("A label name."),
            "include_closed": {
                "type": "boolean",
                "description": "Include done, canceled and duplicate (default false).",
            },
            "limit": _integer("At most this many (default 25, max 100).", 1, 100),
        }),  # fmt: skip
        list_tickets,
    ),
    Tool(
        "get",
        "One ticket in full: description, comments, history, links and followers.",
        _schema({"ticket": TICKET}, ("ticket",)),
        get_ticket,
    ),
    Tool(
        "create",
        "File a new ticket as the signed-in user, who becomes its reporter. Lands in "
        "triage unless a state is given. Check tickets_list for a duplicate first.",
        _schema({
            "title": _string("Short summary."),
            "description": _string("Markdown: what happened, what was expected, how to reproduce."),
            "priority": _integer("1 urgent, 2 high, 3 medium (default), 4 low, 0 none.", 0, 4),
            "assignee": _string("Name or email of a team member; omit to leave unassigned."),
            "labels": LABELS,
            "state": _string("Starting lane, a state key from team (default: first board lane)."),
        }, ("title",)),  # fmt: skip
        create,
        read_only=False,
    ),
    Tool(
        "update",
        "Change any of title, description, priority, state, assignee or labels; omitted "
        "fields stay as they are. assignee 'none' unassigns. labels replaces the set. "
        "Everyone following the ticket is told.",
        _schema({
            "ticket": TICKET,
            "title": _string("New title."),
            "description": _string("New description (markdown); replaces the old one."),
            "priority": _integer("1 urgent, 2 high, 3 medium, 4 low, 0 none.", 0, 4),
            "state": _string("New lane: a state key from team."),
            "assignee": _string("Name or email of a team member, or 'none'."),
            "labels": {**LABELS, "description": "The full set of label names."},
        }, ("ticket",)),  # fmt: skip
        update,
        read_only=False,
    ),
    Tool(
        "comment",
        "Add a markdown comment as the signed-in user. Everyone following is told.",
        _schema(
            {"ticket": TICKET, "body": _string("The comment, in markdown.")}, ("ticket", "body")
        ),
        comment,
        read_only=False,
    ),
    Tool(
        "link",
        "Relate ticket to other: related, blocks (ticket blocks other) or duplicate "
        "(ticket duplicates other, which also closes ticket as duplicate).",
        _schema(
            {"ticket": TICKET, "other": _string("The other ticket."), "kind": _enum("How.", KINDS)},
            ("ticket", "other", "kind"),
        ),
        link,
        read_only=False,
    ),
    Tool(
        "unlink",
        "Remove every link between ticket and other, either direction.",
        _schema({"ticket": TICKET, "other": _string("The other ticket.")}, ("ticket", "other")),
        unlink,
        read_only=False,
    ),
)


def register_tools(
    register: Callable[[str, str, dict, Callable[..., dict]], Any], prefix: str = "tickets_"
) -> list[str]:
    """Hand every tool to the host's `register(name, description, input_schema, handler)`.
    Returns the names registered.

    Not in client mode: tickets live on the hub, so connect assistants to the hub."""
    from django.core.exceptions import ImproperlyConfigured

    from . import conf

    if conf.mode() == "client":
        raise ImproperlyConfigured(
            "dev_tickets is in client mode: tickets live on the hub. "
            "Connect AI assistants to the hub's MCP server instead."
        )
    names = []
    for tool in TOOLS:
        name = f"{prefix}{tool.name}"
        register(name, tool.description, tool.input_schema, tool.handler)
        names.append(name)
    return names

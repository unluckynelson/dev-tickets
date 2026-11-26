"""Write resolvers. Each asks for the request's actor (`actor.require`), which is a
local user who passed `CAN_ACCESS` or a person a hub client vouches for; every
change goes through `service`, which validates it, logs it and tells the subscribers.
A hub client with a read-only key gets no mutation at all."""

from __future__ import annotations

import re

import strawberry

from . import lanes, notify, service, titles
from .actor import Actor, require
from .models import TicketLabel
from .service import KEEP, TicketError
from .types import (
    BoardIssueType,
    IssueCommentType,
    IssueDetailType,
    TicketLabelType,
    TicketStateType,
    card_for,
    comment_type,
    issue_detail,
    label_type,
    state_type_of,
)

_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _guard(info: strawberry.Info) -> Actor:
    return require(info.context.request, write=True)


def _keep(value):
    return KEEP if value is strawberry.UNSET else value


def _labels(ids):
    return KEEP if ids is strawberry.UNSET or ids is None else service.labels_or_refuse(ids)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_dev_ticket(
        self,
        info: strawberry.Info,
        title: str = "",
        description: str = "",
        priority: int = 3,
        assignee_id: str | None = strawberry.UNSET,
        label_ids: list[str] | None = strawberry.UNSET,
        page_url: str = "",
    ) -> BoardIssueType:
        """`assignee_id` unset falls back to DEFAULT_ASSIGNEE; an explicit
        null leaves it unassigned. A blank title is written from the description
        (`titles.title_for`), which is then required."""
        actor = _guard(info)
        if not title.strip():
            if not description.strip():
                raise TicketError("Describe the problem or the request.")
            title = titles.title_for(description, info.context.request)
        if assignee_id is strawberry.UNSET:
            assignee = service.default_assignee()
        else:
            assignee = service.member_or_refuse(assignee_id) if assignee_id else None
        labels = (
            [] if label_ids in (strawberry.UNSET, None) else service.labels_or_refuse(label_ids)
        )
        ticket = service.create_ticket(
            user=actor, title=title, description=description, priority=priority,
            assignee=assignee, labels=labels, page_url=page_url,
            context_label=actor.context_label,
        )  # fmt: skip
        return card_for(ticket)

    @strawberry.mutation
    def update_dev_ticket(
        self,
        info: strawberry.Info,
        id: str,
        title: str | None = strawberry.UNSET,
        description: str | None = strawberry.UNSET,
        priority: int | None = strawberry.UNSET,
        label_ids: list[str] | None = strawberry.UNSET,
    ) -> IssueDetailType:
        """Edit what a ticket says. Lane and assignee have their own mutations."""
        actor = _guard(info)
        ticket = service.ticket_or_refuse(id)
        service.update_ticket(
            ticket, actor, title=_keep(title), description=_keep(description),
            priority=_keep(priority), labels=_labels(label_ids),
        )  # fmt: skip
        return issue_detail(ticket, actor.person)

    @strawberry.mutation
    def move_dev_ticket(self, info: strawberry.Info, id: str, state_id: str) -> BoardIssueType:
        actor = _guard(info)
        ticket = service.update_ticket(service.ticket_or_refuse(id), actor, state=state_id)
        return card_for(ticket)

    @strawberry.mutation
    def assign_dev_ticket(
        self, info: strawberry.Info, id: str, assignee_id: str | None
    ) -> BoardIssueType:
        """An explicit null unassigns."""
        actor = _guard(info)
        assignee = service.member_or_refuse(assignee_id) if assignee_id else None
        ticket = service.update_ticket(service.ticket_or_refuse(id), actor, assignee=assignee)
        return card_for(ticket)

    @strawberry.mutation
    def comment_on_dev_ticket(self, info: strawberry.Info, id: str, body: str) -> IssueCommentType:
        actor = _guard(info)
        comment = service.add_comment(service.ticket_or_refuse(id), actor, body)
        return comment_type(comment, actor.person)

    @strawberry.mutation
    def edit_dev_ticket_comment(
        self, info: strawberry.Info, id: str, body: str
    ) -> IssueCommentType:
        actor = _guard(info)
        return comment_type(service.edit_comment(id, actor, body), actor.person)

    @strawberry.mutation
    def delete_dev_ticket_comment(self, info: strawberry.Info, id: str) -> bool:
        actor = _guard(info)
        service.delete_comment(id, actor)
        return True

    @strawberry.mutation
    def link_dev_tickets(
        self, info: strawberry.Info, id: str, other_id: str, kind: str = "related"
    ) -> IssueDetailType:
        actor = _guard(info)
        ticket = service.ticket_or_refuse(id)
        service.add_relation(ticket, actor, service.ticket_or_refuse(other_id), kind)
        return issue_detail(ticket, actor.person)

    @strawberry.mutation
    def unlink_dev_tickets(
        self, info: strawberry.Info, id: str, relation_id: str
    ) -> IssueDetailType:
        actor = _guard(info)
        ticket = service.ticket_or_refuse(id)
        service.remove_relation(relation_id, actor)
        return issue_detail(ticket, actor.person)

    @strawberry.mutation
    def delete_dev_ticket_attachment(
        self, info: strawberry.Info, id: str, attachment_id: str
    ) -> IssueDetailType:
        actor = _guard(info)
        ticket = service.ticket_or_refuse(id)
        service.delete_attachment(attachment_id, actor)
        return issue_detail(ticket, actor.person)

    @strawberry.mutation
    def subscribe_dev_ticket(self, info: strawberry.Info, id: str, on: bool) -> bool:
        actor = _guard(info)
        service.subscribe(service.ticket_or_refuse(id), actor, on)
        return on

    @strawberry.mutation
    def mark_dev_tickets_seen(self, info: strawberry.Info, id: str | None = None) -> int:
        """Mark the bell read -- all of it, or one ticket's rows. Returns what is
        still unread."""
        actor = _guard(info)
        ticket = service.ticket_or_refuse(id) if id else None
        notify.mark_read(actor.person, ticket.pk if ticket else None)
        return actor.person.notifications.filter(read_at__isnull=True).count()

    @strawberry.mutation
    def set_dev_ticket_email(self, info: strawberry.Info, on: bool) -> bool:
        actor = _guard(info)
        prefs = service.prefs_for(actor)
        prefs.email_updates = on
        prefs.save()
        return on

    @strawberry.mutation
    def save_dev_ticket_label(
        self, info: strawberry.Info, name: str, color: str, id: str | None = None
    ) -> TicketLabelType:
        _guard(info)
        name = name.strip()
        if not name or len(name) > 60:
            raise TicketError("A label needs a name of up to 60 characters.")
        if not _COLOUR.match(color):
            raise TicketError("Colour must be like #4EA7FC.")
        label = TicketLabel.objects.filter(pk=id).first() if id else TicketLabel()
        if label is None:
            raise TicketError("No such label.")
        if TicketLabel.objects.filter(name__iexact=name).exclude(pk=label.pk).exists():
            raise TicketError(f"There is already a label called {name}.")
        label.name, label.color = name, color
        label.save()
        return label_type(label)

    @strawberry.mutation
    def delete_dev_ticket_label(self, info: strawberry.Info, id: str) -> bool:
        """Takes the label off every ticket that has it."""
        _guard(info)
        TicketLabel.objects.filter(pk=id).delete()
        return True

    # --- lanes (Settings) ------------------------------------------------------

    @strawberry.mutation
    def save_dev_ticket_lane(
        self, info: strawberry.Info, name: str, type: str, on_board: bool = True,
        id: str | None = None,
    ) -> TicketStateType:  # fmt: skip
        """Add a lane (no id; it goes last) or rename / retype one."""
        _guard(info)
        return state_type_of(lanes.save_lane(key=id, name=name, type=type, on_board=on_board))

    @strawberry.mutation
    def reorder_dev_ticket_lanes(
        self, info: strawberry.Info, ids: list[str]
    ) -> list[TicketStateType]:
        _guard(info)
        return [state_type_of(lane) for lane in lanes.reorder_lanes(ids)]

    @strawberry.mutation
    def delete_dev_ticket_lane(
        self, info: strawberry.Info, id: str, move_to: str | None = None
    ) -> int:
        """Remove a lane; its tickets move to `move_to` first. Returns how many moved."""
        actor = _guard(info)
        return lanes.delete_lane(id, move_to=move_to, actor=actor.person)

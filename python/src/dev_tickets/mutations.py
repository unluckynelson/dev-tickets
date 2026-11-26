"""Write resolvers. Each checks `CAN_ACCESS`; every change goes through `service`,
which validates it, logs it and tells the subscribers."""

from __future__ import annotations

import re

import strawberry

from . import notify, service, titles
from .models import TicketLabel
from .permissions import access_required, context_label
from .service import KEEP, TicketError
from .types import (
    BoardIssueType,
    IssueCommentType,
    IssueDetailType,
    TicketLabelType,
    card_for,
    comment_type,
    issue_detail,
    label_type,
)

_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _guard(info: strawberry.Info):
    return access_required(info.context.request.user)


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
        user = _guard(info)
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
            user=user, title=title, description=description, priority=priority,
            assignee=assignee, labels=labels, page_url=page_url,
            context_label=context_label(info.context.request),
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
        user = _guard(info)
        ticket = service.ticket_or_refuse(id)
        service.update_ticket(
            ticket, user, title=_keep(title), description=_keep(description),
            priority=_keep(priority), labels=_labels(label_ids),
        )  # fmt: skip
        return issue_detail(ticket, user)

    @strawberry.mutation
    def move_dev_ticket(self, info: strawberry.Info, id: str, state_id: str) -> BoardIssueType:
        user = _guard(info)
        ticket = service.update_ticket(service.ticket_or_refuse(id), user, state=state_id)
        return card_for(ticket)

    @strawberry.mutation
    def assign_dev_ticket(
        self, info: strawberry.Info, id: str, assignee_id: str | None
    ) -> BoardIssueType:
        """An explicit null unassigns."""
        user = _guard(info)
        assignee = service.member_or_refuse(assignee_id) if assignee_id else None
        ticket = service.update_ticket(service.ticket_or_refuse(id), user, assignee=assignee)
        return card_for(ticket)

    @strawberry.mutation
    def comment_on_dev_ticket(self, info: strawberry.Info, id: str, body: str) -> IssueCommentType:
        user = _guard(info)
        comment = service.add_comment(service.ticket_or_refuse(id), user, body)
        return comment_type(comment, user)

    @strawberry.mutation
    def edit_dev_ticket_comment(
        self, info: strawberry.Info, id: str, body: str
    ) -> IssueCommentType:
        user = _guard(info)
        return comment_type(service.edit_comment(id, user, body), user)

    @strawberry.mutation
    def delete_dev_ticket_comment(self, info: strawberry.Info, id: str) -> bool:
        user = _guard(info)
        service.delete_comment(id, user)
        return True

    @strawberry.mutation
    def link_dev_tickets(
        self, info: strawberry.Info, id: str, other_id: str, kind: str = "related"
    ) -> IssueDetailType:
        user = _guard(info)
        ticket = service.ticket_or_refuse(id)
        service.add_relation(ticket, user, service.ticket_or_refuse(other_id), kind)
        return issue_detail(ticket, user)

    @strawberry.mutation
    def unlink_dev_tickets(
        self, info: strawberry.Info, id: str, relation_id: str
    ) -> IssueDetailType:
        user = _guard(info)
        ticket = service.ticket_or_refuse(id)
        service.remove_relation(relation_id, user)
        return issue_detail(ticket, user)

    @strawberry.mutation
    def delete_dev_ticket_attachment(
        self, info: strawberry.Info, id: str, attachment_id: str
    ) -> IssueDetailType:
        user = _guard(info)
        ticket = service.ticket_or_refuse(id)
        service.delete_attachment(attachment_id, user)
        return issue_detail(ticket, user)

    @strawberry.mutation
    def subscribe_dev_ticket(self, info: strawberry.Info, id: str, on: bool) -> bool:
        user = _guard(info)
        service.subscribe(service.ticket_or_refuse(id), user, on)
        return on

    @strawberry.mutation
    def mark_dev_tickets_seen(self, info: strawberry.Info, id: str | None = None) -> int:
        """Mark the bell read -- all of it, or one ticket's rows. Returns what is
        still unread."""
        user = _guard(info)
        ticket = service.ticket_or_refuse(id) if id else None
        notify.mark_read(user, ticket.pk if ticket else None)
        return user.dev_ticket_notifications.filter(read_at__isnull=True).count()

    @strawberry.mutation
    def set_dev_ticket_email(self, info: strawberry.Info, on: bool) -> bool:
        user = _guard(info)
        prefs = service.prefs_for(user)
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

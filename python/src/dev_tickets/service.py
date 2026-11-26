"""Every write to a ticket goes through here: the GraphQL mutations, the MCP tools
and the attachment view all call these, so each change is validated once, logged
once as a `TicketEvent` and fanned out once to the people subscribed.

Callers check access first (`permissions`); these functions assume a team member.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone

from . import conf, notify, states
from .models import (
    DevTicket,
    TicketAttachment,
    TicketComment,
    TicketEvent,
    TicketLabel,
    TicketPreferences,
    TicketRelation,
    TicketSubscription,
)

Kind = TicketEvent.Kind

MAX_TITLE = 300
MAX_TEXT = 20_000
MAX_URL = 1000


class TicketError(PermissionDenied):
    """A refused change, worded for whoever made it (a person or an assistant)."""


class _Keep:
    """ "Leave this field alone" for `update_ticket`: None is a real value (unassign)."""

    def __repr__(self):
        return "KEEP"


KEEP: Any = _Keep()


def display_name(user) -> str:
    if user is None:
        return ""
    return user.get_full_name() or user.get_username()


# --- lookups ------------------------------------------------------------------


def find_ticket(ref) -> DevTicket | None:
    """A ticket by "DEV-12" or by number. Ids and identifiers both resolve, so a
    URL, a pasted identifier and an MCP argument all work."""
    number = states.parse_identifier(str(ref))
    if number is None:
        return None
    return DevTicket.objects.filter(number=number).first()


def ticket_or_refuse(ref) -> DevTicket:
    ticket = find_ticket(ref)
    if ticket is None:
        raise TicketError(f"No ticket {ref}.")
    return ticket


def team_members():
    """Who may hold a ticket: the `TEAM` hook's people, active ones only."""
    return (
        conf.hook("TEAM")()
        .filter(is_active=True)
        .order_by("first_name", "last_name", "pk")
    )


def member_or_refuse(user_id) -> Any:
    found = team_members().filter(pk=user_id).first() if str(user_id).isdigit() else None
    if found is None:
        raise TicketError("That person is not on the team.")
    return found


def find_member(text: str | None):
    """A team member by id, email, username or name, for the MCP tools and settings.
    None when nobody matches or the match is ambiguous."""
    text = (text or "").strip()
    if not text:
        return None
    people = list(team_members())
    for test in (
        lambda u: str(u.pk) == text,
        lambda u: (getattr(u, "email", "") or "").lower() == text.lower(),
        lambda u: u.get_username().lower() == text.lower(),
        lambda u: display_name(u).lower() == text.lower(),
        lambda u: (getattr(u, "first_name", "") or "").lower() == text.lower(),
    ):
        hits = [u for u in people if test(u)]
        if len(hits) == 1:
            return hits[0]
        if hits:
            return None
    return None


def default_assignee():
    return find_member(conf.get("DEFAULT_ASSIGNEE"))


def labels_or_refuse(ids: Iterable) -> list[TicketLabel]:
    wanted = {str(i) for i in ids}
    found = [lbl for lbl in TicketLabel.objects.all() if str(lbl.pk) in wanted]
    if len(found) != len(wanted):
        raise TicketError("Unknown label.")
    return found


def prefs_for(user) -> TicketPreferences:
    obj, _ = TicketPreferences.objects.get_or_create(user=user)
    return obj


# --- events and subscriptions ---------------------------------------------------


def subscribe(ticket: DevTicket, user, on: bool = True) -> None:
    if user is None:
        return
    if on:
        TicketSubscription.objects.get_or_create(ticket=ticket, user=user)
    else:
        TicketSubscription.objects.filter(ticket=ticket, user=user).delete()


def _record(ticket, actor, kind, old="", new="", comment=None) -> TicketEvent:
    event = TicketEvent.objects.create(
        ticket=ticket, actor=actor, kind=kind, old=str(old)[:300], new=str(new)[:300],
        comment=comment,
    )  # fmt: skip
    notify.fan_out(event)
    return event


def _clean_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        raise TicketError("A ticket needs a title.")
    if len(title) > MAX_TITLE:
        raise TicketError(f"Title is limited to {MAX_TITLE} characters.")
    return title


def _clean_text(text: str, what: str = "Description") -> str:
    text = text or ""
    if len(text) > MAX_TEXT:
        raise TicketError(f"{what} is too long.")
    return text


def _check_priority(priority: int) -> int:
    if priority not in states.PRIORITY_LABELS:
        raise TicketError("Unknown priority (0 none, 1 urgent, 2 high, 3 medium, 4 low).")
    return priority


def _check_state(state: str) -> str:
    if state not in states.BY_KEY:
        raise TicketError(f"Unknown state {state!r}; one of {', '.join(states.BY_KEY)}.")
    return state


# --- tickets --------------------------------------------------------------------


def _next_number() -> int:
    return (DevTicket.objects.aggregate(n=Max("number"))["n"] or 0) + 1


def create_ticket(
    *,
    user,
    title: str,
    description: str = "",
    priority: int = 3,
    assignee=None,
    labels: Iterable[TicketLabel] = (),
    state: str = states.TRIAGE,
    page_url: str = "",
    context_label: str = "",
) -> DevTicket:
    """File a ticket as `user`. The number is the next free one; two people filing
    at once collide on the unique constraint and the loser takes the next."""
    title = _clean_title(title)
    description = _clean_text(description)
    _check_priority(priority)
    _check_state(state)
    for _attempt in range(5):
        try:
            with transaction.atomic():
                ticket = DevTicket.objects.create(
                    number=_next_number(), title=title, description=description,
                    priority=priority, state=state, assignee=assignee, reported_by=user,
                    page_url=(page_url or "")[:MAX_URL],
                    context_label=(context_label or "")[:150],
                    closed_at=timezone.now() if state in states.CLOSED_KEYS else None,
                )  # fmt: skip
                break
        except IntegrityError:
            continue
    else:
        raise TicketError("Could not number the ticket; try again.")

    with transaction.atomic():
        if labels:
            ticket.labels.set(labels)
        subscribe(ticket, user)
        subscribe(ticket, assignee)
        _record(ticket, user, Kind.CREATED, new=ticket.title)
    return ticket


def update_ticket(
    ticket: DevTicket,
    user,
    *,
    title=KEEP,
    description=KEEP,
    priority=KEEP,
    state=KEEP,
    assignee=KEEP,
    labels=KEEP,
) -> DevTicket:
    """Change any of the given fields; KEEP leaves one alone. Each real change is an
    event, so a save that changes nothing tells nobody anything."""
    with transaction.atomic():
        ticket = DevTicket.objects.select_for_update().get(pk=ticket.pk)
        events: list[tuple] = []
        fields: list[str] = []

        if title is not KEEP:
            title = _clean_title(title)
            if title != ticket.title:
                events.append((Kind.TITLE, ticket.title, title))
                ticket.title = title
                fields.append("title")
        if description is not KEEP:
            description = _clean_text(description)
            if description != ticket.description:
                events.append((Kind.DESCRIPTION, "", ""))
                ticket.description = description
                fields.append("description")
        if priority is not KEEP and _check_priority(priority) != ticket.priority:
            events.append((
                Kind.PRIORITY, states.PRIORITY_LABELS[ticket.priority],
                states.PRIORITY_LABELS[priority],
            ))  # fmt: skip
            ticket.priority = priority
            fields.append("priority")
        if state is not KEEP and _check_state(state) != ticket.state:
            events.append((Kind.STATE, ticket.state_name, states.state_name(state)))
            ticket.state = state
            ticket.state_changed_at = timezone.now()
            ticket.closed_at = timezone.now() if state in states.CLOSED_KEYS else None
            fields += ["state", "state_changed_at", "closed_at"]
        if assignee is not KEEP and getattr(assignee, "pk", None) != ticket.assignee_id:
            events.append((Kind.ASSIGNEE, display_name(ticket.assignee), display_name(assignee)))
            ticket.assignee = assignee
            fields.append("assignee")
            subscribe(ticket, assignee)

        if fields:
            ticket.save(update_fields=[*fields, "updated_at"])
        if labels is not KEEP:
            before = sorted(lbl.name for lbl in ticket.labels.all())
            after = sorted(lbl.name for lbl in labels)
            if before != after:
                ticket.labels.set(labels)
                events.append((Kind.LABELS, ", ".join(before), ", ".join(after)))
                if not fields:
                    ticket.save(update_fields=["updated_at"])
        for kind, old, new in events:
            _record(ticket, user, kind, old, new)
    return ticket


# --- comments -------------------------------------------------------------------


def add_comment(ticket: DevTicket, user, body: str) -> TicketComment:
    body = _clean_text(body, "Comment").strip()
    if not body:
        raise TicketError("A comment cannot be empty.")
    with transaction.atomic():
        comment = TicketComment.objects.create(ticket=ticket, author=user, body=body)
        subscribe(ticket, user)
        _record(ticket, user, Kind.COMMENT, new=body[:300], comment=comment)
        DevTicket.objects.filter(pk=ticket.pk).update(updated_at=timezone.now())
    return comment


def _own_comment(comment_id, user) -> TicketComment:
    comment = (
        TicketComment.objects.filter(pk=comment_id).select_related("ticket").first()
        if str(comment_id).isdigit()
        else None
    )
    if comment is None:
        raise TicketError("No such comment.")
    if comment.author_id != user.pk:
        raise TicketError("Only its author can change a comment.")
    return comment


def edit_comment(comment_id, user, body: str) -> TicketComment:
    comment = _own_comment(comment_id, user)
    body = _clean_text(body, "Comment").strip()
    if not body:
        raise TicketError("A comment cannot be empty; delete it instead.")
    if body != comment.body:
        comment.body = body
        comment.edited_at = timezone.now()
        comment.save()
    return comment


def delete_comment(comment_id, user) -> DevTicket:
    comment = _own_comment(comment_id, user)
    ticket = comment.ticket
    comment.delete()
    return ticket


# --- relations ------------------------------------------------------------------


def add_relation(ticket: DevTicket, user, other: DevTicket, kind: str) -> TicketRelation:
    if kind not in states.RELATION_KINDS:
        raise TicketError(f"Unknown relation; one of {', '.join(states.RELATION_KINDS)}.")
    if other.pk == ticket.pk:
        raise TicketError("A ticket cannot relate to itself.")
    existing = TicketRelation.objects.filter(
        Q(ticket=ticket, other=other) | Q(ticket=other, other=ticket), kind=kind
    ).first()
    if existing is not None:
        return existing
    with transaction.atomic():
        relation = TicketRelation.objects.create(ticket=ticket, other=other, kind=kind)
        _record(ticket, user, Kind.RELATION, new=f"{kind} {other.identifier}")
        # Marking a duplicate closes it.
        if kind == states.DUPLICATE_OF and ticket.state != states.DUPLICATE:
            update_ticket(ticket, user, state=states.DUPLICATE)
    return relation


def remove_relation(relation_id, user) -> DevTicket:
    relation = (
        TicketRelation.objects.filter(pk=relation_id).select_related("ticket", "other").first()
        if str(relation_id).isdigit()
        else None
    )
    if relation is None:
        raise TicketError("No such link.")
    ticket = relation.ticket
    with transaction.atomic():
        relation.delete()
        _record(ticket, user, Kind.RELATION, old=f"{relation.kind} {relation.other.identifier}")
    return ticket


# --- attachments ----------------------------------------------------------------


def max_attachment_bytes() -> int:
    return int(conf.get("MAX_ATTACHMENT_MB")) * 1024 * 1024


def add_attachment(ticket: DevTicket, user, upload) -> TicketAttachment:
    if upload.size > max_attachment_bytes():
        raise TicketError(
            f"That file is too large; the limit is {conf.get('MAX_ATTACHMENT_MB')} MB."
        )
    name = (getattr(upload, "name", "") or "file")[-200:]
    with transaction.atomic():
        attachment = TicketAttachment(
            ticket=ticket, name=name, content_type=(upload.content_type or "")[:100],
            size=upload.size, uploaded_by=user,
        )  # fmt: skip
        attachment.file.save(name, upload, save=False)
        attachment.save()
        _record(ticket, user, Kind.ATTACHMENT, new=name)
    return attachment


def delete_attachment(attachment_id, user) -> DevTicket:
    attachment = (
        TicketAttachment.objects.filter(pk=attachment_id).select_related("ticket").first()
        if str(attachment_id).isdigit()
        else None
    )
    if attachment is None:
        raise TicketError("No such attachment.")
    ticket = attachment.ticket
    storage, stored = attachment.file.storage, attachment.file.name
    with transaction.atomic():
        attachment.delete()
        _record(ticket, user, Kind.ATTACHMENT, old=attachment.name)
        # The bytes go only once the row is gone for good.
        transaction.on_commit(lambda: storage.delete(stored))
    return ticket

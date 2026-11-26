"""Who hears about a ticket change, and how.

Every `TicketEvent` becomes one `TicketNotification` per subscriber other than the
person who made the change -- the reporter, the assignee, everyone who commented,
and anyone who subscribed by hand. That row is the bell. So the person who reported
a bug is the one told it is fixed, and nobody is told about their own change.

Email follows the bell, never leads it: `deliver` (run every minute by the
`devtickets_notify` command) mails a person a digest of what is still unread after
`EMAIL_AFTER`, so someone with the app open sees it there and gets no mail, and a
burst of changes is one message. People switch it off from the bell.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from . import conf, digest
from .models import TicketEvent, TicketNotification, TicketPreferences, TicketSubscription

logger = logging.getLogger(__name__)

# An unread notification older than this is not worth a mail any more.
EMAIL_UNTIL = timedelta(days=2)

Kind = TicketEvent.Kind


def email_after() -> timedelta:
    return timedelta(seconds=int(conf.get("EMAIL_AFTER")))


def _name(user) -> str:
    if user is None:
        return "Someone"
    return user.get_full_name() or user.get_username()


def summary(event: TicketEvent) -> str:
    """One line saying what happened, for the bell and the email."""
    who = _name(event.actor)
    if event.kind == Kind.CREATED:
        return f"{who} reported it"
    if event.kind == Kind.STATE:
        return f"{who} moved it to {event.new}"
    if event.kind == Kind.ASSIGNEE:
        return f"{who} assigned it to {event.new}" if event.new else f"{who} unassigned it"
    if event.kind == Kind.PRIORITY:
        return f"{who} set priority to {event.new}"
    if event.kind == Kind.TITLE:
        return f"{who} renamed it"
    if event.kind == Kind.DESCRIPTION:
        return f"{who} edited the description"
    if event.kind == Kind.LABELS:
        return f"{who} set labels to {event.new}" if event.new else f"{who} cleared the labels"
    if event.kind == Kind.RELATION:
        return f"{who} linked {event.new}" if event.new else f"{who} unlinked {event.old}"
    if event.kind == Kind.COMMENT:
        return f"{who} commented: {event.new[:140]}"
    if event.kind == Kind.ATTACHMENT:
        return f"{who} attached {event.new}" if event.new else f"{who} removed {event.old}"
    return f"{who} changed it"


def fan_out(event: TicketEvent) -> int:
    """Tell every subscriber but the actor. Returns how many were told."""
    users = (
        TicketSubscription.objects.filter(ticket_id=event.ticket_id, user__is_active=True)
        .exclude(user_id=event.actor_id)
        .values_list("user_id", flat=True)
    )
    rows = [TicketNotification(user_id=uid, event=event) for uid in users]
    TicketNotification.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


def mark_read(user, ticket_id=None) -> int:
    rows = TicketNotification.objects.filter(user=user, read_at__isnull=True)
    if ticket_id is not None:
        rows = rows.filter(event__ticket_id=ticket_id)
    return rows.update(read_at=timezone.now())


def deliver(now=None) -> int:
    """Email each person what is unread and old enough. Returns messages sent.

    Everything considered is stamped `emailed_at`, sent or not (email off, no
    address, already read), so nothing is considered twice. A failed send is logged
    and stamped too: one bad address must not mail the others every minute forever.
    """
    now = now or timezone.now()
    due = (
        TicketNotification.objects.filter(
            emailed_at__isnull=True, created_at__lte=now - email_after()
        )
        .select_related(
            "user", "event__actor", "event__comment", "event__ticket__assignee",
            "event__ticket__reported_by",
        )  # fmt: skip
        .prefetch_related("event__ticket__labels")
        .order_by("created_at", "pk")
    )
    by_user: dict = defaultdict(list)
    for n in due:
        by_user[n.user].append(n)
    if not by_user:
        return 0

    muted = set(
        TicketPreferences.objects.filter(user__in=list(by_user), email_updates=False).values_list(
            "user_id", flat=True
        )
    )
    send = conf.hook("SEND_MAIL")
    sent = 0
    for user, rows in by_user.items():
        fresh = [n for n in rows if n.read_at is None and n.created_at > now - EMAIL_UNTIL]
        address = getattr(user, "email", "")
        if fresh and address and user.pk not in muted:
            context = {
                "name": getattr(user, "first_name", "") or user.get_username(),
                "items": digest.items(fresh),
                "team_name": conf.get("TEAM_NAME"),
            }
            try:
                send(
                    _subject(fresh),
                    render_to_string("dev_tickets/email/digest.txt", context),
                    render_to_string("dev_tickets/email/digest.html", context),
                    [address],
                )
                sent += 1
            except Exception:  # noqa: BLE001 -- logged; the others still go
                logger.exception("Dev-ticket digest to %s failed", user.pk)
        with transaction.atomic():
            TicketNotification.objects.filter(pk__in=[n.pk for n in rows]).update(emailed_at=now)
    return sent


def _subject(rows) -> str:
    tickets = {n.event.ticket_id for n in rows}
    if len(tickets) == 1:
        t = rows[0].event.ticket
        return f"[{t.identifier}] {t.title}"[:150]
    return f"{len(rows)} updates on {len(tickets)} dev tickets"

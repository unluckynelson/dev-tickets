"""Editing lanes (`TicketState`): add, rename, retype, reorder and remove.

A lane is known by its `key`, which tickets store and which never changes, so a
rename moves nothing. What a lane *means* is its type: changing a lane between an
open and a closed type opens or closes every ticket in it, so `closed_at` stays true.
Removing a lane that still holds tickets needs somewhere to put them; they move
there with a history entry each, and nobody is notified -- it is housekeeping, not
news. The board always keeps at least one lane, which is where new tickets land.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from . import states
from .models import DevTicket, TicketEvent, TicketState
from .service import TicketError

MAX_NAME = 40


def _clean_name(name: str, lane: TicketState) -> str:
    name = (name or "").strip()
    if not name or len(name) > MAX_NAME:
        raise TicketError(f"A lane needs a name of up to {MAX_NAME} characters.")
    if TicketState.objects.filter(name__iexact=name).exclude(pk=lane.pk).exists():
        raise TicketError(f"There is already a lane called {name}.")
    return name


def _new_key(name: str) -> str:
    base = slugify(name).replace("-", "_")[:16] or "lane"
    key, n = base, 1
    while TicketState.objects.filter(key=key).exists():
        n += 1
        key = f"{base[:16]}_{n}"
    return key


def _lane(key: str) -> TicketState:
    lane = TicketState.objects.filter(key=key).first()
    if lane is None:
        raise TicketError("No such lane.")
    return lane


def _sync_closed(lane: TicketState) -> None:
    """Open or close the lane's tickets to match its type."""
    tickets = DevTicket.objects.filter(state=lane.key)
    if lane.type in states.CLOSED_TYPES:
        tickets.filter(closed_at__isnull=True).update(closed_at=timezone.now())
    else:
        tickets.exclude(closed_at__isnull=True).update(closed_at=None)


@transaction.atomic
def save_lane(
    *, key: str | None, name: str, type: str, on_board: bool = True
) -> TicketState:
    """Add a lane (no key; it goes last) or change one."""
    lane = _lane(key) if key else TicketState()
    lane.name = _clean_name(name, lane)
    if type not in states.TYPE_KEYS:
        kinds = ", ".join(sorted(states.TYPE_KEYS))
        raise TicketError(f"Unknown lane type {type!r}; one of {kinds}.")
    if lane.pk and not on_board and lane.on_board:
        others = TicketState.objects.filter(on_board=True).exclude(pk=lane.pk)
        if not others.exists():
            raise TicketError("The board needs at least one lane.")
    retyped = lane.pk is not None and lane.type != type
    lane.type, lane.on_board = type, on_board
    if not lane.pk:
        lane.key = _new_key(lane.name)
        last = TicketState.objects.order_by("-position").first()
        lane.position = (last.position + 1) if last else 0
    lane.save()
    if retyped:
        _sync_closed(lane)
    return lane


@transaction.atomic
def reorder_lanes(keys: list[str]) -> list[TicketState]:
    """Put the lanes in this order. Every lane must be named exactly once."""
    lanes = {lane.key: lane for lane in TicketState.objects.all()}
    if sorted(keys) != sorted(lanes):
        raise TicketError("The new order must list every lane once.")
    for position, key in enumerate(keys):
        if lanes[key].position != position:
            lanes[key].position = position
            lanes[key].save(update_fields=["position", "updated_at"])
    return [lanes[k] for k in keys]


@transaction.atomic
def delete_lane(key: str, *, move_to: str | None, actor=None) -> int:
    """Remove a lane, first moving its tickets to `move_to`. Returns how many moved."""
    lane = _lane(key)
    if lane.on_board and not TicketState.objects.filter(on_board=True).exclude(pk=lane.pk).exists():
        raise TicketError("The board needs at least one lane.")
    tickets = list(DevTicket.objects.filter(state=lane.key))
    if tickets:
        if not move_to:
            raise TicketError(
                f"{lane.name} still holds {len(tickets)} ticket(s); choose a lane to move them to."
            )
        target = _lane(move_to)
        if target.pk == lane.pk:
            raise TicketError("Move the tickets to a different lane.")
        now = timezone.now()
        closed = target.type in states.CLOSED_TYPES
        for ticket in tickets:
            ticket.state, ticket.state_changed_at = target.key, now
            if closed and ticket.closed_at is None:
                ticket.closed_at = now
            elif not closed:
                ticket.closed_at = None
        DevTicket.objects.bulk_update(tickets, ["state", "state_changed_at", "closed_at"])
        TicketEvent.objects.bulk_create(
            TicketEvent(
                ticket=t, actor=actor, kind=TicketEvent.Kind.STATE, old=lane.name, new=target.name
            )
            for t in tickets
        )
    lane.delete()
    return len(tickets)

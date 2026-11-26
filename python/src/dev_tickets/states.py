"""The ticket vocabulary: workflow states (lanes), priorities and relation kinds.

Lanes are data (`models.TicketState`), edited in the board's Settings: a team can
add, rename, reorder or retire them. Each has a `type`, which is what the code
relies on rather than any lane's name -- a lane of a closed type closes a ticket,
the first board lane is where new tickets land, and the first lane of type
"duplicate" is where linking a duplicate sends it. The default seven are seeded by
migration 0003 with the keys below, which tickets imported before lanes were data
already hold.

Reads go through `_lanes()`, cached for the length of a request (cleared on
request start and on every lane change), since `is_closed` is asked per ticket.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from . import conf


@dataclass(frozen=True)
class State:
    key: str
    name: str
    type: str
    # Off the board: closed without being done. Still reachable from the dialog.
    on_board: bool = True


TRIAGE = "triage"
BACKLOG = "backlog"
TODO = "todo"
IN_PROGRESS = "in_progress"
DONE = "done"
CANCELED = "canceled"
DUPLICATE = "duplicate"

# What a lane means. The board colours a lane by its type.
TYPES = (
    ("triage", "Triage"),
    ("backlog", "Backlog"),
    ("unstarted", "To do"),
    ("started", "In progress"),
    ("completed", "Done"),
    ("canceled", "Canceled"),
    ("duplicate", "Duplicate"),
)
TYPE_CHOICES = list(TYPES)
TYPE_KEYS = frozenset(k for k, _ in TYPES)
CLOSED_TYPES = frozenset({"completed", "canceled", "duplicate"})

# The lanes a new install starts with (migration 0003).
DEFAULT_STATES: tuple[State, ...] = (
    State(TRIAGE, "Triage", "triage"),
    State(BACKLOG, "Backlog", "backlog"),
    State(TODO, "Todo", "unstarted"),
    State(IN_PROGRESS, "In Progress", "started"),
    State(DONE, "Done", "completed"),
    State(CANCELED, "Canceled", "canceled", on_board=False),
    State(DUPLICATE, "Duplicate", "duplicate", on_board=False),
)

# Outside a request (commands, tests) the cache also expires on its own.
_TTL = 1.0
_cache: tuple[float, tuple[State, ...]] | None = None


def clear_cache(*_args, **_kwargs) -> None:
    global _cache
    _cache = None


def _lanes() -> tuple[State, ...]:
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _TTL:
        return _cache[1]
    from .models import TicketState

    lanes = TicketState.objects.order_by("position", "pk")
    rows = tuple(State(r.key, r.name, r.type, r.on_board) for r in lanes)
    _cache = (now, rows)
    return rows


def all_states() -> tuple[State, ...]:
    return _lanes()


def board_states() -> list[State]:
    return [s for s in _lanes() if s.on_board]


def by_key() -> dict[str, State]:
    return {s.key: s for s in _lanes()}


def closed_keys() -> frozenset[str]:
    return frozenset(s.key for s in _lanes() if s.type in CLOSED_TYPES)


def default_key() -> str:
    """Where a new ticket lands: the first lane on the board."""
    lanes = board_states() or list(_lanes())
    return lanes[0].key if lanes else TRIAGE


def duplicate_key() -> str | None:
    """The lane a ticket marked as a duplicate moves to; None if there is none."""
    return next((s.key for s in _lanes() if s.type == "duplicate"), None)


# 0 sorts last; the scale most trackers use, so imported priorities keep their meaning.
PRIORITIES = [
    (0, "No priority"),
    (1, "Urgent"),
    (2, "High"),
    (3, "Medium"),
    (4, "Low"),
]
PRIORITY_LABELS = dict(PRIORITIES)

# Relation kinds, read from the ticket that holds the row. "blocks" is directed: the
# other ticket sees it as "blocked by". "duplicate" means this one duplicates that one.
RELATED = "related"
BLOCKS = "blocks"
DUPLICATE_OF = "duplicate"
RELATION_KINDS = (RELATED, BLOCKS, DUPLICATE_OF)


def prefix() -> str:
    return str(conf.get("PREFIX")).upper()


def identifier(number: int) -> str:
    return f"{prefix()}-{number}"


def parse_identifier(value: str) -> int | None:
    """12 from "DEV-12", "dev-12" or "12"; None for anything else."""
    text = (value or "").strip().upper()
    lead = f"{prefix()}-"
    if text.startswith(lead):
        text = text[len(lead) :]
    return int(text) if text.isdigit() else None


def state_name(key: str) -> str:
    lane = by_key().get(key)
    return lane.name if lane else key


def state_type(key: str) -> str:
    lane = by_key().get(key)
    return lane.type if lane else ""

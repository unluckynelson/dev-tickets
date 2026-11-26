"""The ticket vocabulary: workflow states, priorities and relation kinds. Code, not data.

Each state has a `type` -- the board colours its lanes by type, and `CLOSED_TYPES`
is what "done" means to the bell and to reports. A fixed list rather than a table:
a code-defined state can be relied on by name (`TRIAGE` is where new tickets land),
and it is versioned with the package rather than drifting per install.
"""

from __future__ import annotations

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

STATES: tuple[State, ...] = (
    State(TRIAGE, "Triage", "triage"),
    State(BACKLOG, "Backlog", "backlog"),
    State(TODO, "Todo", "unstarted"),
    State(IN_PROGRESS, "In Progress", "started"),
    State(DONE, "Done", "completed"),
    State(CANCELED, "Canceled", "canceled", on_board=False),
    State(DUPLICATE, "Duplicate", "duplicate", on_board=False),
)
BY_KEY = {s.key: s for s in STATES}
CHOICES = [(s.key, s.name) for s in STATES]

CLOSED_TYPES = frozenset({"completed", "canceled", "duplicate"})
CLOSED_KEYS = frozenset(s.key for s in STATES if s.type in CLOSED_TYPES)

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
    return BY_KEY[key].name if key in BY_KEY else key


def state_type(key: str) -> str:
    return BY_KEY[key].type if key in BY_KEY else ""

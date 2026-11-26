"""Who is acting on this request, decided once and kept on the request.

Every resolver and file view asks `actor_for(request)` and never looks at
`request.user` itself, so the same code serves a person signed in to this install
and a person a hub client vouches for (`hub.py` sets the actor before the schema
runs). An actor without a `person` was refused, and `refusal` says why in the words
the package has always used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import PermissionDenied

ATTRIBUTE = "_dev_tickets_actor"

SIGNED_OUT = "Authentication required."
NO_ACCESS = "You do not have access to dev tickets."
READ_ONLY = "This hub client's key is read-only."


@dataclass
class Actor:
    person: Any = None  # a models.Person, or None when refused
    refusal: str = ""
    context_label: str = ""
    # The hub client this came through; blank for this install's own users.
    source: str = ""
    read_only: bool = False
    # The local user, when there is one (never for a remote actor).
    user: Any = None


def actor_for(request) -> Actor:
    cached = getattr(request, ATTRIBUTE, None)
    if cached is not None:
        return cached
    from . import people
    from .permissions import can_access, context_label

    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        actor = Actor(refusal=SIGNED_OUT)
    elif not can_access(user):
        actor = Actor(refusal=NO_ACCESS, user=user)
    else:
        actor = Actor(
            person=people.for_user(user), context_label=context_label(request), user=user
        )
    setattr(request, ATTRIBUTE, actor)
    return actor


def set_actor(request, actor: Actor) -> None:
    setattr(request, ATTRIBUTE, actor)


def require(request, *, write: bool = False) -> Actor:
    """The actor, or PermissionDenied for anyone refused (or a read-only key writing)."""
    actor = actor_for(request)
    if actor.person is None:
        raise PermissionDenied(actor.refusal or NO_ACCESS)
    if write and actor.read_only:
        raise PermissionDenied(READ_ONLY)
    return actor

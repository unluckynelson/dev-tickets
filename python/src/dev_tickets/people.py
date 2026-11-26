"""Who someone is: turning a signed-in user, or a hub client's actor, into a `Person`.

Everything in the package that names somebody (reporter, assignee, follower,
commenter, the bell) holds a `Person`, in every mode. Two ways in:

- `for_user(user)`: someone signed in to this install. The person linked to that
  user, else an unlinked one with the same email (a remote actor met earlier, who
  now turns out to be a local user too), else a new one.
- `for_remote(...)`: someone a hub client vouches for. Matched on email only.

Both refresh the name and avatar, since the source knows best. Whether a person can
be assigned (`is_team`) comes from the `TEAM` hook for a linked person and from the
client's word for an unlinked one: the hub knows its own users better than any client.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import conf
from .actor import Actor
from .models import Person

# last_seen_at is a hint, not a log: write it at most this often.
SEEN_EVERY = timedelta(minutes=1)


def normalise_email(value: Any) -> str:
    return str(value or "").strip().lower()


def user_name(user) -> str:
    full = (user.get_full_name() or "").strip() if hasattr(user, "get_full_name") else ""
    return full or user.get_username()


def _team_user_ids() -> set:
    return set(conf.hook("TEAM")().filter(is_active=True).values_list("pk", flat=True))


def _seen(person: Person, now) -> bool:
    if person.last_seen_at is None or now - person.last_seen_at >= SEEN_EVERY:
        person.last_seen_at = now
        return True
    return False


def _create(**fields) -> Person:
    """Create, or find the row a concurrent request created a moment ago."""
    try:
        with transaction.atomic():
            return Person.objects.create(**fields)
    except IntegrityError:
        email = fields.get("email")
        found = Person.objects.filter(email=email).first() if email else None
        if found is None:
            found = Person.objects.filter(user=fields.get("user")).first()
        if found is None:
            raise
        return found


def for_user(user, *, team_ids: set | None = None, seen: bool = True) -> Person:
    """The person for a local user, created or linked on first sight."""
    email = normalise_email(getattr(user, "email", ""))
    name = user_name(user)
    in_team = user.pk in (team_ids if team_ids is not None else _team_user_ids())
    now = timezone.now()

    person = Person.objects.filter(user=user).first()
    if person is None and email:
        candidate = Person.objects.filter(email=email).first()
        # Two local users sharing an address: the second gets a person of its own.
        if candidate is not None and candidate.user_id in (None, user.pk):
            person = candidate
    if person is None:
        taken = bool(email) and Person.objects.filter(email=email).exists()
        return _create(
            user=user, email=None if taken else (email or None), name=name, is_team=in_team,
            last_seen_at=now if seen else None,
        )  # fmt: skip

    changed = []
    if person.user_id != user.pk:
        person.user = user
        changed.append("user")
    if person.name != name:
        person.name = name
        changed.append("name")
    if email and person.email != email and not Person.objects.filter(email=email).exists():
        person.email = email
        changed.append("email")
    if person.is_team != in_team:
        person.is_team = in_team
        changed.append("is_team")
    if seen and _seen(person, now):
        changed.append("last_seen_at")
    if changed:
        person.save(update_fields=[*changed, "updated_at"])
    return person


def for_remote(email: str, name: str = "", avatar: str = "", team: bool = False) -> Person:
    """The person a hub client vouches for. Email is the identity; it must be set."""
    email = normalise_email(email)
    if not email:
        raise ValueError("A remote actor needs an email address.")
    name = str(name or "").strip()[:200]
    avatar = str(avatar or "").strip()[:1000]
    now = timezone.now()
    person = Person.objects.filter(email=email).first()
    if person is None:
        return _create(email=email, name=name, avatar_url=avatar, is_team=bool(team),
                       last_seen_at=now)  # fmt: skip

    changed = []
    # A linked person's name and team come from this install's own user.
    if person.user_id is None:
        if name and person.name != name:
            person.name = name
            changed.append("name")
        if person.is_team != bool(team):
            person.is_team = bool(team)
            changed.append("is_team")
    if avatar and person.avatar_url != avatar:
        person.avatar_url = avatar
        changed.append("avatar_url")
    if _seen(person, now):
        changed.append("last_seen_at")
    if changed:
        person.save(update_fields=[*changed, "updated_at"])
    return person


def team():
    """Who can hold a ticket: the `TEAM` hook's users (synced into people here, so
    someone who has never opened the board can still be assigned) and every remote
    person whose client said they are on the team."""
    team_users = list(conf.hook("TEAM")().filter(is_active=True))
    ids = {u.pk for u in team_users}
    for user in team_users:
        for_user(user, team_ids=ids, seen=False)
    # A linked person who left the team stops being assignable at once.
    Person.objects.filter(user__isnull=False, is_team=True).exclude(user__in=ids).update(
        is_team=False
    )
    return (
        Person.objects.filter(is_team=True)
        .exclude(user__is_active=False)
        .select_related("user")
        .order_by("name", "email", "pk")
    )


def as_person(who) -> Person | None:
    """A Person from a Person, an Actor or a local user (None stays None)."""
    if who is None or isinstance(who, Person):
        return who
    if isinstance(who, Actor):
        return who.person
    return for_user(who)


def source_of(who) -> str:
    """The hub client a change came through ("" for this install's own people)."""
    return who.source if isinstance(who, Actor) else ""

"""Dev tickets: a product team's issue tracker, kept in the app it tracks.

Tickets are global to the install, not owned by a tenant or workspace: they are
tooling for the people building the product, gated by `CAN_ACCESS`. Where a host
app has tenants, the one a report was filed *from* is kept as `context_label`, a
denormalised name, so it reads correctly after the tenant is renamed or removed.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from . import conf, states

User = settings.AUTH_USER_MODEL


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Person(TimeStampedModel):
    """Someone who reports, holds, follows or comments on tickets.

    Not the auth user: a hub serves several environments, and user 7 on staging is
    not user 7 in production, so a foreign key to the user model cannot say who
    somebody is. People are known by email instead, stored lower-cased so two
    spellings are one person. A person met through this install's own login is
    linked to that user (`user`); one met only through a client's API key is not.
    A local user and a remote actor with the same email are the same person.

    `email` is null for a local user who has none, so several of those can exist.
    """

    email = models.EmailField(max_length=254, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200, blank=True)
    avatar_url = models.URLField(max_length=1000, blank=True)
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="dev_tickets_person"
    )
    # Can be assigned a ticket. For a linked person this follows the `TEAM` hook; for
    # a remote one, what its client last said.
    is_team = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "email", "pk"]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower() or None
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.name or self.email or ""

    @property
    def is_active(self) -> bool:
        return self.user is None or self.user.is_active

    def __str__(self):
        return self.display_name or f"Person {self.pk}"


class HubClient(TimeStampedModel):
    """An environment allowed to use this hub's API, with its own key.

    Only the key's SHA-256 is kept; `key_prefix` (its first 8 characters) is there
    so a list of clients can show which key is which without storing the key.
    `source` is the label stamped on everything done through it ("staging").
    """

    name = models.CharField(max_length=100, unique=True)
    source = models.CharField(max_length=60)
    key_hash = models.CharField(max_length=64, unique=True)
    key_prefix = models.CharField(max_length=8)
    read_only = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TicketState(TimeStampedModel):
    """A lane: a workflow state tickets move through. Data, edited in Settings.

    `key` is what a ticket stores and never changes, so renaming a lane moves no
    ticket. `type` says what the lane *means* -- where a new ticket lands is the
    first board lane, and a ticket in a lane of a closed type (`states.CLOSED_TYPES`)
    is closed: the bell calls it done and it stamps `closed_at`. Lanes not on the
    board (canceled, duplicate) are still reachable from the ticket dialog.
    """

    key = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=40, unique=True)
    type = models.CharField(max_length=12, choices=states.TYPE_CHOICES, default="unstarted")
    on_board = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.name


class TrackerSettings(TimeStampedModel):
    """The one row of settings changed from the board's Settings dialog instead of
    the host's `DEV_TICKETS`: which mode this install runs in and, as a client, how
    it reaches its hub. A value the host sets in `DEV_TICKETS` wins and shows as
    locked (`conf.get`).

    The client's key is stored as given, since it must be sent to the hub on every
    request; the hub keeps only its hash.
    """

    mode = models.CharField(max_length=12, blank=True)
    hub_url = models.URLField(max_length=500, blank=True)
    hub_api_key = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=60, blank=True)

    class Meta:
        verbose_name_plural = "tracker settings"

    @classmethod
    def load(cls) -> TrackerSettings:
        return cls.objects.order_by("pk").first() or cls()


class TicketLabel(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    color = models.CharField(max_length=9, default="#888888")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DevTicket(TimeStampedModel):
    """One ticket. `number` is the N in PREFIX-N, unique and never reused."""

    number = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)  # markdown
    state = models.CharField(max_length=20, default=states.TRIAGE)  # a TicketState.key
    priority = models.PositiveSmallIntegerField(default=3)  # see states.PRIORITIES
    labels = models.ManyToManyField(TicketLabel, blank=True, related_name="tickets")

    # Who raised it -- the person, not whichever account or key filed it. An import
    # from another tracker sets this to the real reporter.
    reported_by = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="reported_tickets"
    )
    assignee = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    # When the state last moved. The board orders a lane by it (newest arrival on
    # top) and reports read cycle time off it with `closed_at`.
    state_changed_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    # Where the reporter was standing when they logged it.
    page_url = models.CharField(max_length=1000, blank=True)
    context_label = models.CharField(max_length=150, blank=True)
    # Which hub client it was filed through ("staging"); blank when filed here.
    source = models.CharField(max_length=60, blank=True)

    # Provenance for a ticket imported from another tracker. Null for every ticket
    # born here; unique so a re-run import cannot duplicate one.
    external_id = models.CharField(max_length=64, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def identifier(self) -> str:
        return states.identifier(self.number)

    @property
    def is_closed(self) -> bool:
        return self.state in states.closed_keys()

    @property
    def state_name(self) -> str:
        return states.state_name(self.state)

    @property
    def state_type(self) -> str:
        return states.state_type(self.state)

    def __str__(self):
        return f"{self.identifier} {self.title}"


class TicketComment(TimeStampedModel):
    ticket = models.ForeignKey(DevTicket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    body = models.TextField()  # markdown
    source = models.CharField(max_length=60, blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    external_id = models.CharField(max_length=64, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"Comment on {self.ticket.identifier}"


class TicketRelation(TimeStampedModel):
    """`ticket` relates to / blocks / duplicates `other`. Stored once, read both ways."""

    ticket = models.ForeignKey(DevTicket, on_delete=models.CASCADE, related_name="relations_out")
    other = models.ForeignKey(DevTicket, on_delete=models.CASCADE, related_name="relations_in")
    kind = models.CharField(
        max_length=12, choices=[(k, k) for k in states.RELATION_KINDS], default=states.RELATED
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["ticket", "other", "kind"], name="dev_tickets_unique_relation"
            ),
            models.CheckConstraint(
                condition=~models.Q(ticket=models.F("other")),
                name="dev_tickets_relation_not_self",
            ),
        ]


class TicketSubscription(TimeStampedModel):
    """Who hears about a ticket. Reporter, assignee and commenters are added for
    them; anyone may subscribe or leave by hand."""

    ticket = models.ForeignKey(DevTicket, on_delete=models.CASCADE, related_name="subscriptions")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="subscriptions")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["ticket", "person"], name="dev_tickets_unique_subscription"
            ),
        ]


class TicketEvent(TimeStampedModel):
    """One change to a ticket: its history, and what notifications point at.

    `old`/`new` are display text (a state's name, a person's name), frozen as they
    read when it happened, so renaming a label does not rewrite the history.
    """

    class Kind(models.TextChoices):
        CREATED = "created", "Created"
        STATE = "state", "State"
        ASSIGNEE = "assignee", "Assignee"
        PRIORITY = "priority", "Priority"
        TITLE = "title", "Title"
        DESCRIPTION = "description", "Description"
        LABELS = "labels", "Labels"
        RELATION = "relation", "Relation"
        COMMENT = "comment", "Comment"
        ATTACHMENT = "attachment", "Attachment"

    ticket = models.ForeignKey(DevTicket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    source = models.CharField(max_length=60, blank=True)
    old = models.CharField(max_length=300, blank=True)
    new = models.CharField(max_length=300, blank=True)
    comment = models.ForeignKey(
        TicketComment, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["created_at", "pk"]


class TicketNotification(models.Model):
    """One event, for one person: the bell's row, and the email's.

    Made for every subscriber but the actor (`notify.fan_out`). `read_at` clears it
    from the badge; `emailed_at` is set by the delivery run whether or not mail went
    out, so a person with email off is not reconsidered every minute.
    """

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="notifications")
    event = models.ForeignKey(TicketEvent, on_delete=models.CASCADE, related_name="notifications")
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["person", "event"], name="dev_tickets_unique_notification"
            ),
        ]
        indexes = [
            models.Index(fields=["person", "read_at"], name="dev_tickets_notif_unread_idx")
        ]

    def __str__(self):
        return f"{self.event} for {self.person_id}"


class TicketPreferences(models.Model):
    """Per person. Only email for now; the bell is always on."""

    person = models.OneToOneField(Person, on_delete=models.CASCADE, related_name="prefs")
    email_updates = models.BooleanField(default=True)

    def __str__(self):
        return f"Ticket preferences of {self.person_id}"


def _attachment_path(attachment: TicketAttachment, filename: str) -> str:
    from pathlib import Path
    from uuid import uuid4

    suffix = Path(filename).suffix.lower()[:10]
    return f"dev_tickets/{attachment.ticket_id}/{uuid4().hex}{suffix}"


def _attachment_storage():
    from django.core.files.storage import storages

    return storages[conf.get("STORAGE")]


class TicketAttachment(TimeStampedModel):
    """A screenshot or file on a ticket. Served only through `views.attachment_file`."""

    ticket = models.ForeignKey(DevTicket, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=_attachment_path, storage=_attachment_storage, max_length=200)
    name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["created_at", "pk"]

"""Manage the installs allowed to use this hub's API.

    manage.py devtickets_client add staging [--source staging] [--read-only]
    manage.py devtickets_client list
    manage.py devtickets_client rotate staging
    manage.py devtickets_client revoke staging

`add` and `rotate` print the key once; only its hash is kept.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dev_tickets import conf, hub
from dev_tickets.models import HubClient


class Command(BaseCommand):
    help = "Add, list, rotate or revoke the API keys other installs use to reach this hub."

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)
        add = sub.add_parser("add", help="Make a client and print its key.")
        add.add_argument("name")
        add.add_argument("--source", help="Label stamped on its tickets (default: the name).")
        add.add_argument("--read-only", action="store_true", help="Refuse its mutations.")
        sub.add_parser("list", help="Every client and when it was last used.")
        for action, text in (("revoke", "Stop a client's key working."),
                             ("rotate", "Give a client a new key; the old one stops.")):
            sub.add_parser(action, help=text).add_argument("name")

    def handle(self, *args, **options):
        if conf.mode() == "client":
            raise CommandError(
                "This install is a dev-tickets client; manage API keys on the hub."
            )
        action = options["action"]
        if action == "list":
            return self._list()
        if action == "add":
            return self._add(options["name"], options["source"], options["read_only"])
        client = HubClient.objects.filter(name=options["name"]).first()
        if client is None:
            raise CommandError(f"No client called {options['name']!r}.")
        if action == "revoke":
            if client.revoked_at is None:
                client.revoked_at = timezone.now()
                client.save(update_fields=["revoked_at", "updated_at"])
            self.stdout.write(f"Revoked {client.name}; its key no longer works.")
            return None
        key = hub.issue(client)
        client.revoked_at = None
        client.save()
        self.stdout.write(f"New key for {client.name} (the old one no longer works):")
        self.stdout.write(key)
        return None

    def _add(self, name, source, read_only):
        name = name.strip()
        if not name or len(name) > 100:
            raise CommandError("A client needs a name of up to 100 characters.")
        if HubClient.objects.filter(name=name).exists():
            raise CommandError(f"There is already a client called {name!r}; use rotate.")
        client = HubClient(name=name, source=(source or name).strip()[:60], read_only=read_only)
        key = hub.issue(client)
        client.save()
        self.stdout.write(
            f"Added {name} (source {client.source!r}"
            + (", read-only" if read_only else "")
            + "). Its key, shown once:"
        )
        self.stdout.write(key)

    def _list(self):
        clients = list(HubClient.objects.all())
        if not clients:
            self.stdout.write("No clients.")
            return
        for c in clients:
            used = c.last_used_at.strftime("%Y-%m-%d %H:%M") if c.last_used_at else "never"
            flags = [f for f, on in (("read-only", c.read_only),
                                     ("REVOKED", c.revoked_at is not None)) if on]  # fmt: skip
            self.stdout.write(
                f"{c.name}\tsource={c.source}\tkey={c.key_prefix}…\tlast used {used}"
                + (f"\t{' '.join(flags)}" if flags else "")
            )

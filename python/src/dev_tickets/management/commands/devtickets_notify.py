"""Email each person a digest of what is still unread. Run it once a minute."""

from django.core.management.base import BaseCommand

from dev_tickets import notify


class Command(BaseCommand):
    help = "Send dev-ticket digest emails for notifications left unread."

    def handle(self, *args, **options):
        sent = notify.deliver()
        if options["verbosity"] > 1 or sent:
            self.stdout.write(f"Sent {sent} digest(s).")

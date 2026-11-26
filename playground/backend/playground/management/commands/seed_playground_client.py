"""Seed the client playground with people only: tickets live on the hub.

Priya exists only here; Maya shares her address with the hub's Maya, so the hub
treats the two accounts as one person. Safe to run again.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed the client playground with two people (no tickets: those are on the hub)."

    def handle(self, *args, **options):
        users = get_user_model()
        for username, first, last, email in (
            ("priya", "Priya", "Shah", "priya@example.com"),
            ("maya", "Maya", "Okafor", "maya@example.com"),
        ):
            user, made = users.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": email,
                          "is_staff": True, "is_superuser": True},
            )  # fmt: skip
            if made:
                user.set_password("playground")
                user.save()
        self.stdout.write("Client people: Priya Shah, Maya Okafor (shared with the hub).")

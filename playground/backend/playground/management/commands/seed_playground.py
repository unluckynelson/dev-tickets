"""Seed the playground: four people and a dozen tickets (the ones in the README screenshots).

Idempotent only in the sense that it refuses to run twice: delete playground.sqlite3 to
start again.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dev_tickets import service
from dev_tickets.models import DevTicket, TicketLabel


class Command(BaseCommand):
    help = "Seed the playground with sample people and tickets."

    def handle(self, *args, **options):
        if DevTicket.objects.exists():
            raise CommandError(
                "Already seeded. Delete playground.sqlite3 to start again."
            )
        U = get_user_model()

        def su(username, first, last, pw="playground"):
            u, _ = U.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@example.com",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            u.set_password(pw)
            u.save()
            return u

        maya = su("maya", "Maya", "Okafor")
        sam = su("sam", "Sam", "Rivera")
        lena = su("lena", "Lena", "Fischer")
        tom = su("tom", "Tom", "Nakamura")
        L = {
            n: TicketLabel.objects.get_or_create(name=n, defaults={"color": c})[0]
            for n, c in [
                ("Bug", "#ef4444"),
                ("Feature", "#8b5cf6"),
                ("Improvement", "#3b82f6"),
                ("UX", "#f59e0b"),
                ("Performance", "#10b981"),
            ]
        }
        T = [
            (
                "Export button does nothing on Safari",
                "Clicking **Export** on the invoices page shows the spinner, then nothing downloads.\n\nSteps:\n1. Open Invoices in Safari 18\n2. Filter by October\n3. Click Export\n\nWorks in Chrome.",
                1,
                "in_progress",
                sam,
                maya,
                ["Bug"],
                "/invoices?month=2026-10",
                "Acme Logistics",
            ),
            (
                "Add dark mode to the settings page",
                "The rest of the app follows the system theme, but Settings stays white.",
                3,
                "todo",
                lena,
                tom,
                ["UX", "Improvement"],
                "/settings",
                "Northwind",
            ),
            (
                "Search is slow with more than 10k customers",
                "Typing in the customer search takes 3-4 seconds per keystroke on large accounts. Probably needs an index on `name`.",
                2,
                "todo",
                sam,
                maya,
                ["Performance"],
                "/customers",
                "Globex",
            ),
            (
                "Allow bulk-assigning tasks",
                "Managers want to tick several tasks and assign them to one person at once.",
                3,
                "backlog",
                None,
                lena,
                ["Feature"],
                "/tasks",
                "Acme Logistics",
            ),
            (
                "Date picker opens off-screen on small laptops",
                'On a 13" screen the calendar opens below the fold.',
                4,
                "triage",
                None,
                tom,
                ["Bug", "UX"],
                "/schedule",
                "Initech",
            ),
            (
                "Welcome email has a broken logo",
                "Gmail shows a broken image where the logo should be.",
                2,
                "triage",
                None,
                maya,
                ["Bug"],
                "/admin/emails",
                "",
            ),
            (
                "CSV import: remember column mapping",
                "Every month we map the same 14 columns by hand.",
                3,
                "backlog",
                None,
                lena,
                ["Improvement"],
                "/import",
                "Northwind",
            ),
            (
                "Session expires while typing a long note",
                "Lost a paragraph after 30 minutes of typing.",
                2,
                "done",
                maya,
                tom,
                ["Bug"],
                "/notes/41",
                "Globex",
            ),
            (
                "Show who changed a record and when",
                "An audit line under each form: 'Last changed by … on …'.",
                3,
                "done",
                sam,
                lena,
                ["Feature"],
                "/customers/12",
                "Initech",
            ),
            (
                "Keyboard shortcut to file a ticket",
                "Something like `Shift+?` to open the ticket button from anywhere.",
                4,
                "backlog",
                None,
                sam,
                ["Feature", "UX"],
                "/",
                "",
            ),
            (
                "Totals row ignores filtered rows",
                "The totals at the bottom of the report include rows the filter hides.",
                1,
                "in_progress",
                lena,
                maya,
                ["Bug"],
                "/reports/sales",
                "Acme Logistics",
            ),
            (
                "Translate the onboarding screens",
                "Spanish and Portuguese first.",
                4,
                "todo",
                tom,
                lena,
                ["Feature"],
                "/welcome",
                "",
            ),
        ]
        made = []
        for title, desc, pri, st, asg, rep, labels, url, ctx in T:
            t = service.create_ticket(
                user=rep,
                title=title,
                description=desc,
                priority=pri,
                assignee=asg,
                labels=[L[x] for x in labels],
                state=st,
                page_url="https://app.example.com" + url,
                context_label=ctx,
            )
            made.append(t)
        t0 = made[0]
        service.add_comment(
            t0,
            sam,
            "Reproduced. Safari blocks the download because it starts after an `await`. Moving it into the click handler.",
        )
        service.add_comment(
            t0,
            maya,
            "Thanks! Our accountant needs October's export by Friday, is that doable?",
        )
        service.add_comment(
            t0, sam, "Yes, fix is in review. Should be live tomorrow morning."
        )
        service.add_relation(t0, sam, made[10], "related")
        service.add_relation(made[2], sam, made[3], "blocks")
        # spread timestamps
        now = timezone.now()
        for i, t in enumerate(made):
            DevTicket.objects.filter(pk=t.pk).update(
                created_at=now - timedelta(days=i * 2 + 1, hours=i),
                state_changed_at=now - timedelta(days=i, hours=3 * i),
            )
        self.stdout.write(
            f"Seeded {DevTicket.objects.count()} tickets. Sign in at /playground/."
        )

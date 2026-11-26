"""Tickets: who may touch them, how they are numbered, and who hears about changes."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from dev_tickets import notify, people, service, states
from dev_tickets.models import (
    DevTicket,
    TicketAttachment,
    TicketNotification,
    TicketRelation,
)
from tests.conftest import PNG, browser, csrf_header, gql

pytestmark = pytest.mark.django_db

User = get_user_model()


def unread(user) -> list[str]:
    return [
        notify.summary(n.event)
        for n in TicketNotification.objects.filter(
            person=people.for_user(user), read_at__isnull=True
        ).order_by("pk")
    ]


def upload(client, ticket, name, body, kind):
    return client.post(
        f"/devtickets-files/{ticket.identifier}/",
        {"file": SimpleUploadedFile(name, body, kind)},
        headers=csrf_header(client),
    )


# --- who may ------------------------------------------------------------------


def test_people_outside_the_team_reach_nothing(outsider):
    client = browser(outsider)
    for query in ("{ devTicketBoard { teamName } }", "{ devTickets { unreadCount } }"):
        assert gql(client, query)["errors"]
    result = gql(client, 'mutation { createDevTicket(title: "x") { id } }')
    assert result["errors"] and not DevTicket.objects.exists()


def test_a_request_without_the_csrf_token_is_refused(lead):
    client = browser(lead)
    response = client.post(
        "/devtickets/graphql/", data='{"query": "{ devTickets { unreadCount } }"}',
        content_type="application/json",
    )  # fmt: skip
    assert response.status_code == 403


def test_attachments_are_team_only_and_never_render_html_inline(lead, outsider):
    ticket = service.create_ticket(user=lead, title="Broken")
    client = browser(lead)
    response = upload(client, ticket, "x.html", b"<script>alert(1)</script>", "text/html")
    assert response.status_code == 201
    pk = response.json()["ids"][0]

    served = client.get(f"/devtickets-files/attachment/{pk}/")
    assert served["Content-Type"] == "application/octet-stream"
    assert served["Content-Disposition"].startswith("attachment")

    assert browser(outsider).get(f"/devtickets-files/attachment/{pk}/").status_code == 403
    refused = upload(browser(outsider), ticket, "y.png", PNG, "image/png")
    assert refused.status_code == 403 and TicketAttachment.objects.count() == 1


def test_an_image_is_shown_inline_and_records_who_uploaded_it(lead):
    ticket = service.create_ticket(user=lead, title="Broken")
    client = browser(lead)
    pk = upload(client, ticket, "shot.png", PNG, "image/png").json()["ids"][0]
    served = client.get(f"/devtickets-files/attachment/{pk}/")
    assert served["Content-Type"] == "image/png"
    assert served["X-Content-Type-Options"] == "nosniff"
    detail = gql(
        client, "query($id: String!) { devTicketDetail(id: $id) { attachments { uploaderName } } }",
        {"id": ticket.identifier},
    )  # fmt: skip
    assert detail["data"]["devTicketDetail"]["attachments"] == [{"uploaderName": "Maya Okafor"}]


def test_a_file_over_the_limit_is_refused(lead, settings):
    settings.DEV_TICKETS = {**settings.DEV_TICKETS, "MAX_ATTACHMENT_MB": 0}
    ticket = service.create_ticket(user=lead, title="Broken")
    response = upload(browser(lead), ticket, "shot.png", PNG, "image/png")
    assert response.status_code == 400 and "too large" in response.json()["problems"][0]


def test_the_cards_cover_is_its_first_image_never_another_file(lead):
    ticket = service.create_ticket(user=lead, title="Broken")
    client = browser(lead)
    board = "{ devTicketBoard { lanes { issues { identifier coverId } } } }"

    def cover():
        lanes = gql(client, board)["data"]["devTicketBoard"]["lanes"]
        return next(i["coverId"] for ln in lanes for i in ln["issues"])

    upload(client, ticket, "log.pdf", b"%PDF-1.4 x", "application/pdf")
    assert cover() is None
    first = upload(client, ticket, "a.png", PNG, "image/png").json()["ids"][0]
    upload(client, ticket, "b.png", PNG, "image/png")
    assert cover() == first


# --- filing and numbering -----------------------------------------------------


def test_new_tickets_continue_imported_numbering_and_name_the_real_reporter(lead, dev):
    DevTicket.objects.create(number=144, title="Imported", external_id="other-144")
    result = gql(
        browser(dev),
        """mutation { createDevTicket(title: "Totals wrong",
        description: "See the report", pageUrl: "http://x/reports/pay") {
        identifier reporterName assigneeName stateName contextLabel } }""",
    )["data"]["createDevTicket"]
    # Default assignee is the configured one; the reporter is who filed it.
    assert result == {
        "identifier": "APP-145",
        "reporterName": "Sam",
        "assigneeName": "Maya Okafor",
        "stateName": "Triage",
        "contextLabel": "",
    }
    ticket = DevTicket.objects.get(number=145)
    followers = ticket.subscriptions.values_list("person__user__username", flat=True)
    assert set(followers) == {"sam", "lead"}
    assert unread(lead) == ["Sam reported it"]
    assert unread(dev) == []


def test_an_explicit_null_assignee_leaves_it_unassigned(lead, dev):
    made = gql(
        browser(dev), 'mutation { createDevTicket(title: "x", assigneeId: null) { assigneeName } }'
    )
    assert made["data"]["createDevTicket"]["assigneeName"] == ""


def test_only_team_members_can_hold_a_ticket(lead, outsider):
    ticket = service.create_ticket(user=lead, title="x")
    result = gql(
        browser(lead),
        "mutation($id: String!, $a: String) { assignDevTicket(id: $id, "
        "assigneeId: $a) { assigneeName } }",
        {"id": ticket.identifier, "a": str(outsider.pk)},
    )
    assert "team" in result["errors"][0]["message"]


def test_two_tickets_filed_back_to_back_get_consecutive_numbers(lead):
    a = service.create_ticket(user=lead, title="one")
    b = service.create_ticket(user=lead, title="two")
    assert (a.identifier, b.identifier) == ("APP-1", "APP-2")


# --- who hears about it -------------------------------------------------------


def test_the_reporter_hears_their_ticket_is_done_and_the_actor_does_not(lead, dev):
    ticket = service.create_ticket(user=dev, title="Export broken", assignee=lead)
    notify.mark_read(lead)

    service.update_ticket(ticket, lead, state=states.IN_PROGRESS)
    service.update_ticket(ticket, lead, state=states.DONE)

    assert unread(dev) == [
        "Maya Okafor moved it to In Progress",
        "Maya Okafor moved it to Done",
    ]
    assert unread(lead) == []
    ticket.refresh_from_db()
    assert ticket.closed_at is not None


def test_a_save_that_changes_nothing_tells_nobody(lead, dev):
    ticket = service.create_ticket(user=dev, title="Same", priority=2)
    service.update_ticket(ticket, lead, title="Same", priority=2, state=states.TRIAGE)
    assert unread(dev) == []


def test_commenting_subscribes_you_so_you_hear_the_reply(lead, dev):
    lena = User.objects.create_superuser("lena", password="x", first_name="Lena")
    ticket = service.create_ticket(user=dev, title="Search slow")
    service.add_comment(ticket, lena, "Same on our account")
    service.add_comment(ticket, lead, "Fixed, please retest")

    assert unread(lena) == ["Maya Okafor commented: Fixed, please retest"]
    assert unread(dev) == [
        "Lena commented: Same on our account",
        "Maya Okafor commented: Fixed, please retest",
    ]

    service.subscribe(ticket, lena, on=False)
    service.add_comment(ticket, lead, "Deployed")
    assert len(unread(lena)) == 1


def test_only_its_author_edits_a_comment(lead, dev):
    ticket = service.create_ticket(user=dev, title="x")
    comment = service.add_comment(ticket, dev, "first")
    with pytest.raises(service.TicketError):
        service.edit_comment(comment.pk, lead, "rewritten")
    service.edit_comment(comment.pk, dev, "second")
    comment.refresh_from_db()
    assert comment.body == "second" and comment.edited_at is not None


def test_opening_the_bell_or_a_ticket_clears_the_badge(lead, dev):
    one = service.create_ticket(user=dev, title="one", assignee=lead)
    service.create_ticket(user=dev, title="two", assignee=lead)
    client = browser(lead)
    assert gql(client, "{ devTickets { unreadCount } }")["data"]["devTickets"]["unreadCount"] == 2
    left = gql(
        client, "mutation($id: String) { markDevTicketsSeen(id: $id) }", {"id": one.identifier}
    )
    assert left["data"]["markDevTicketsSeen"] == 1
    gql(client, "mutation { markDevTicketsSeen }")
    assert not unread(lead)
    feed = gql(client, "{ devTickets { notifications { read } } }")["data"]["devTickets"]
    assert feed["notifications"] == [{"read": True}, {"read": True}]  # listed, just read


def later() -> timezone.datetime:
    return timezone.now() + notify.email_after() + timedelta(seconds=1)


def test_email_is_a_digest_of_what_is_still_unread(lead, dev, mailoutbox):
    ticket = service.create_ticket(user=lead, title="Pay export", assignee=dev)
    service.add_comment(ticket, lead, "Needs the CSV format")
    seen = service.create_ticket(user=lead, title="Already looked at", assignee=dev)
    notify.mark_read(dev, seen.pk)

    assert notify.deliver() == 0  # too fresh: the bell gets the first chance
    assert notify.deliver(now=later()) == 1
    assert len(mailoutbox) == 1
    msg = mailoutbox[0]
    assert msg.to == ["sam@example.com"]
    assert msg.subject == f"[{ticket.identifier}] Pay export"
    assert "Needs the CSV format" in msg.body and "Already looked at" not in msg.body
    assert f"https://app.example.com/admin/dev-tickets/{ticket.identifier}" in msg.body
    assert notify.deliver(now=later()) == 0  # stamped; never twice


def test_email_carries_the_whole_comment_rendered_and_safe(lead, dev, mailoutbox):
    ticket = service.create_ticket(
        user=lead, title="Totals", assignee=dev, description="Steps:\n\n1. Open the report",
    )  # fmt: skip
    long = "**Totals** and **Filters** " + "now agree on the last page. " * 12
    service.add_comment(ticket, lead, long + "<script>alert(1)</script> [see](/reports/5)")
    notify.deliver(now=later())
    html = mailoutbox[0].alternatives[0][0]
    # Whole comment, markdown rendered; script dropped; an in-app link made absolute.
    assert html.count("now agree on the last page.") == 12
    assert "<strong>Totals</strong>" in html and "**Totals**" not in html
    assert "<script" not in html
    assert 'href="https://app.example.com/reports/5"' in html and 'href="/reports' not in html
    assert "<li" in html and "Assignee" in html  # description and ticket facts too
    assert "now agree on the last page. " * 12 in mailoutbox[0].body  # text part in full


def test_email_goes_through_the_send_mail_hook(lead, dev, settings):
    sent = []
    settings.DEV_TICKETS = {
        **settings.DEV_TICKETS,
        "SEND_MAIL": lambda subject, text, html, to: sent.append((subject, to)),
    }
    service.create_ticket(user=lead, title="Hooked", assignee=dev)
    assert notify.deliver(now=later()) == 1
    assert sent == [("[APP-1] Hooked", ["sam@example.com"])]


def test_a_failing_send_is_stamped_and_does_not_stop_the_others(lead, dev, settings):
    lena = User.objects.create_superuser("lena", email="lena@example.com", password="x")
    sent = []

    def send(subject, text, html, to):
        if to == ["sam@example.com"]:
            raise OSError("mailbox full")
        sent.append(to)

    settings.DEV_TICKETS = {**settings.DEV_TICKETS, "SEND_MAIL": send}
    ticket = service.create_ticket(user=lead, title="Two readers", assignee=dev)
    service.subscribe(ticket, lena)
    service.add_comment(ticket, lead, "ping")
    assert notify.deliver(now=later()) == 1
    assert sent == [["lena@example.com"]]
    assert notify.deliver(now=later()) == 0  # the failure is not retried every minute


def test_email_can_be_switched_off(lead, dev, mailoutbox):
    gql(browser(dev), "mutation { setDevTicketEmail(on: false) }")
    service.create_ticket(user=lead, title="x", assignee=dev)
    assert notify.deliver(now=timezone.now() + timedelta(minutes=5)) == 0
    assert not mailoutbox
    assert unread(dev)  # the bell still has it


# --- links --------------------------------------------------------------------


def test_marking_a_duplicate_closes_it_and_both_sides_read_the_link(lead):
    original = service.create_ticket(user=lead, title="Original")
    copy = service.create_ticket(user=lead, title="Copy")
    service.add_relation(copy, lead, original, states.DUPLICATE_OF)
    copy.refresh_from_db()
    assert copy.state == states.DUPLICATE

    q = (
        "query($id: String!) { devTicketDetail(id: $id) "
        "{ relations { label ticket { identifier } } } }"
    )
    seen = gql(browser(lead), q, {"id": original.identifier})["data"]["devTicketDetail"]
    assert seen["relations"] == [{"label": "Duplicated by", "ticket": {"identifier": "APP-2"}}]
    # Linking the same pair again, from the other side, makes no second row.
    service.add_relation(original, lead, copy, states.DUPLICATE_OF)
    assert TicketRelation.objects.count() == 1


def test_canceled_and_duplicate_tickets_are_off_the_board(lead):
    service.create_ticket(user=lead, title="Live")
    service.create_ticket(user=lead, title="Dropped", state=states.CANCELED)
    lanes = gql(browser(lead), "{ devTicketBoard { lanes { id issues { title } } } }")
    lanes = lanes["data"]["devTicketBoard"]["lanes"]
    assert [ln["id"] for ln in lanes] == ["triage", "backlog", "todo", "in_progress", "done"]
    assert [i["title"] for ln in lanes for i in ln["issues"]] == ["Live"]


def test_the_notify_command_sends_the_digest(lead, dev, mailoutbox):
    from django.core.management import call_command

    ticket = service.create_ticket(user=lead, title="Command", assignee=dev)
    TicketNotification.objects.filter(event__ticket=ticket).update(
        created_at=timezone.now() - timedelta(minutes=10)
    )
    call_command("devtickets_notify")
    assert [m.subject for m in mailoutbox] == ["[APP-1] Command"]

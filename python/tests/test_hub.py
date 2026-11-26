"""The hub's API: a client server's key, and the person it says is acting."""

from datetime import timedelta
from urllib.parse import quote

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone

from dev_tickets import hub, people, service
from dev_tickets.models import DevTicket, HubClient, Person, TicketNotification
from tests.conftest import PNG, browser, gql
from tests.hubtools import API, actor, api_gql, api_headers, make_client

pytestmark = pytest.mark.django_db

BOARD = "{ devTicketBoard { lanes { issues { identifier } } } }"
FILE = (
    'mutation { createDevTicket(title: "Export broken", description: "Nothing happens") '
    "{ identifier reporterName source contextLabel } }"
)


def test_no_key_a_wrong_key_or_a_revoked_one_is_turned_away(lead):
    row, key = make_client()
    for sent in (None, "dt_nope"):
        result = api_gql(sent, BOARD, who=actor(), status=401)
        assert "key" in result["errors"][0]["message"]
    assert api_gql(key, BOARD, who=actor())["data"]

    row.revoked_at = timezone.now()
    row.save()
    api_gql(key, BOARD, who=actor(), status=401)


def test_the_api_is_only_there_on_a_hub(lead):
    _, key = make_client()
    response = Client().post(
        API + "graphql/", data="{}", content_type="application/json",
        headers=api_headers(key, actor()),
    )  # fmt: skip
    assert response.status_code == 404


def test_every_request_names_who_is_acting(lead):
    _, key = make_client()
    assert "X-Dev-Tickets-Actor" in api_gql(key, BOARD, status=400)["errors"][0]["message"]
    assert "email" in api_gql(key, BOARD, who=actor(email=""), status=400)["errors"][0]["message"]
    api_gql(key, BOARD, who="not json", status=400)
    assert not Person.objects.exists()


def test_a_read_only_key_reads_and_cannot_write(lead):
    _, key = make_client(read_only=True)
    service.create_ticket(user=lead, title="Existing")
    assert api_gql(key, BOARD, who=actor())["data"]["devTicketBoard"]
    result = api_gql(key, FILE, who=actor())
    assert "read-only" in result["errors"][0]["message"]
    assert DevTicket.objects.count() == 1


def test_last_used_is_stamped_but_not_on_every_request(lead):
    row, key = make_client()
    api_gql(key, BOARD, who=actor())
    row.refresh_from_db()
    first = row.last_used_at
    assert first is not None
    api_gql(key, BOARD, who=actor())
    row.refresh_from_db()
    assert row.last_used_at == first

    HubClient.objects.filter(pk=row.pk).update(last_used_at=first - timedelta(minutes=2))
    api_gql(key, BOARD, who=actor())
    row.refresh_from_db()
    assert row.last_used_at > first - timedelta(minutes=2)


def test_a_remote_person_files_with_source_and_context_and_the_team_hears(lead):
    _, key = make_client(source="staging")
    made = api_gql(key, FILE, who=actor(), context=quote("Bäckerei Müller"))
    assert made["data"]["createDevTicket"] == {
        "identifier": "APP-1", "reporterName": "Priya Shah", "source": "staging",
        "contextLabel": "Bäckerei Müller",
    }  # fmt: skip
    ticket = DevTicket.objects.get()
    assert ticket.reported_by.email == "priya@example.com" and ticket.reported_by.user is None
    assert ticket.events.get().source == "staging"

    # The default assignee (a hub user) hears about it in the hub's own bell.
    bell = gql(browser(lead), "{ devTickets { notifications { summary } } }")
    assert bell["data"]["devTickets"]["notifications"] == [{"summary": "Priya Shah reported it"}]

    # She hears back about a reply, in her own bell, through the API.
    service.add_comment(ticket, lead, "Fixed on master.")
    feed = api_gql(key, "{ devTickets { unreadCount } }", who=actor())
    assert feed["data"]["devTickets"]["unreadCount"] == 1
    assert TicketNotification.objects.filter(person__email="priya@example.com").count() == 1


def test_a_remote_team_member_can_be_assigned_and_others_cannot(lead):
    _, key = make_client()
    api_gql(key, BOARD, who=actor("jo@example.com", "Jo Contractor", team=True))
    api_gql(key, BOARD, who=actor("vee@example.com", "Vee Visitor", team=False))
    config = gql(browser(lead), "{ devSupportConfig { assignees { id name } } }")
    team = {a["name"]: a["id"] for a in config["data"]["devSupportConfig"]["assignees"]}
    assert set(team) == {"Jo Contractor", "Maya Okafor"}

    ticket = service.create_ticket(user=lead, title="x")
    assign = (
        "mutation($id: String!, $a: String) { assignDevTicket(id: $id, assigneeId: $a) "
        "{ assigneeName } }"
    )
    done = gql(browser(lead), assign, {"id": ticket.identifier, "a": team["Jo Contractor"]})
    assert done["data"]["assignDevTicket"]["assigneeName"] == "Jo Contractor"
    vee = str(Person.objects.get(email="vee@example.com").pk)
    refused = gql(browser(lead), assign, {"id": ticket.identifier, "a": vee})
    assert "team" in refused["errors"][0]["message"]


def test_a_hub_user_and_a_remote_actor_with_the_same_email_are_one_person(lead):
    _, key = make_client()
    ticket = service.create_ticket(user=lead, title="Mine")
    detail = "query($id: String!) { devTicketDetail(id: $id) { comments { mine } subscribed } }"
    api_gql(
        key, 'mutation { commentOnDevTicket(id: "APP-1", body: "From staging") { mine } }',
        who=actor("LEAD@example.com", "Someone Else"),
    )  # fmt: skip
    assert Person.objects.filter(email="lead@example.com").count() == 1
    person = people.for_user(lead)
    assert person.name == "Maya Okafor"  # the hub's own user names her, not the client
    seen = gql(browser(lead), detail, {"id": ticket.identifier})["data"]["devTicketDetail"]
    assert seen == {"comments": [{"mine": True}], "subscribed": True}
    # Her own comment, made elsewhere, does not ring her bell here.
    assert not TicketNotification.objects.filter(person=person).exists()


def test_files_go_through_the_api_with_the_same_rules(lead):
    _, key = make_client()
    ticket = service.create_ticket(user=lead, title="Shots")
    with override_settings(DEV_TICKETS={**settings.DEV_TICKETS, "MODE": "hub"}):
        client = Client()
        made = client.post(
            API + f"files/{ticket.identifier}/",
            {"file": [SimpleUploadedFile("shot.png", PNG, "image/png"),
                      SimpleUploadedFile("x.html", b"<script>", "text/html")]},
            headers=api_headers(key, actor()),
        )  # fmt: skip
        assert made.status_code == 201, made.content
        png, html = made.json()["ids"]
        shown = client.get(API + f"files/attachment/{png}/", headers=api_headers(key, actor()))
        assert shown["Content-Type"] == "image/png"
        saved = client.get(API + f"files/attachment/{html}/", headers=api_headers(key, actor()))
        assert saved["Content-Disposition"].startswith("attachment")
        assert client.get(API + f"files/attachment/{png}/").status_code == 401
    assert ticket.attachments.first().uploaded_by.email == "priya@example.com"
    assert hub.hash_key(key) == HubClient.objects.get().key_hash

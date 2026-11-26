"""Client mode end to end: the browser talks to its own backend, which forwards to
the hub. The hub runs in this process (`hubtools.Router`), so both share one test
database; what matters is what crosses the wire and what the browser gets back."""

import json
from io import StringIO
from urllib.parse import unquote

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command

from dev_tickets import client as client_mode
from dev_tickets.mcp import register_tools
from dev_tickets.models import DevTicket, Person, TicketAttachment
from tests.conftest import PNG, browser, csrf_header, gql
from tests.hubtools import Router, make_client

pytestmark = pytest.mark.django_db

User = get_user_model()

FILE = (
    'mutation { createDevTicket(title: "Export broken") '
    "{ identifier reporterName source contextLabel } }"
)


@pytest.fixture
def hub_key(db):
    return make_client(name="staging", source="staging")[1]


@pytest.fixture
def as_client(settings, hub_key, monkeypatch):
    """Switch this install to client mode and route its hub calls in-process."""
    settings.DEV_TICKETS = {
        **settings.DEV_TICKETS, "MODE": "client", "HUB_URL": "https://hub.example.com/",
        "HUB_API_KEY": hub_key, "SOURCE": "staging",
        "CONTEXT_LABEL": lambda request: "Bäckerei Müller",
        "AVATAR": lambda user: f"https://img.example.com/{user.get_username()}.png",
    }  # fmt: skip
    router = Router()
    monkeypatch.setattr(client_mode, "transport", router)
    return router


def test_a_ticket_filed_on_a_client_lands_on_the_hub_with_who_and_where(
    as_client, hub_key, lead, dev
):
    result = gql(browser(dev), FILE)
    assert result["data"]["createDevTicket"] == {
        "identifier": "APP-1", "reporterName": "Sam", "source": "staging",
        "contextLabel": "Bäckerei Müller",
    }  # fmt: skip

    call = as_client.calls[0]
    assert call["url"] == "https://hub.example.com/devtickets/api/v1/graphql/"
    assert call["headers"]["Authorization"] == f"Bearer {hub_key}"
    assert json.loads(call["headers"]["X-Dev-Tickets-Actor"]) == {
        "email": "sam@example.com", "name": "Sam", "avatar": "https://img.example.com/sam.png",
        "team": True,
    }  # fmt: skip
    assert unquote(call["headers"]["X-Dev-Tickets-Context"]) == "Bäckerei Müller"
    assert DevTicket.objects.get().reported_by.email == "sam@example.com"


def test_the_key_never_reaches_the_browser(as_client, dev, hub_key):
    client = browser(dev)
    for query in (FILE, "{ devSupportConfig { enabled assignees { name email } } }"):
        response = client.post(
            "/devtickets/graphql/", data=json.dumps({"query": query}),
            content_type="application/json", headers=csrf_header(client),
        )  # fmt: skip
        assert hub_key.encode() not in response.content
        assert b"hub.example.com" not in response.content


def test_someone_the_client_refuses_never_reaches_the_hub(as_client, outsider):
    client = browser(outsider)
    config = gql(client, "{ devSupportConfig { enabled } }")
    assert config["data"]["devSupportConfig"]["enabled"] is False
    refused = gql(client, "{ devTicketBoard { teamName } }")
    assert refused["errors"][0]["message"] == "You do not have access to dev tickets."
    anonymous = gql(browser(), "{ devTicketBoard { teamName } }")
    assert anonymous["errors"][0]["message"] == "Authentication required."
    assert as_client.calls == [] and not Person.objects.exists()


def test_a_user_without_an_email_is_told_so_and_not_forwarded(as_client):
    nobody = User.objects.create_superuser("nomail", email="", password="x")
    client = browser(nobody)
    assert gql(client, "{ devSupportConfig { enabled } }")["data"]["devSupportConfig"] == {
        "enabled": False
    }
    result = gql(client, FILE)
    assert result["errors"][0]["message"] == client_mode.NO_EMAIL
    assert as_client.calls == []


@pytest.mark.parametrize("router", [Router(down=True), Router(status=503)])
def test_a_hub_that_is_down_is_a_502_with_a_plain_message(as_client, monkeypatch, dev, router):
    monkeypatch.setattr(client_mode, "transport", router)
    client = browser(dev)
    response = client.post(
        "/devtickets/graphql/", data=json.dumps({"query": FILE}),
        content_type="application/json", headers=csrf_header(client),
    )  # fmt: skip
    assert response.status_code == 502
    assert response.json()["errors"][0]["message"] == client_mode.UNREACHABLE


def test_files_go_up_and_come_down_through_the_client(as_client, settings, lead, dev):
    gql(browser(dev), FILE)
    client = browser(dev)
    made = client.post(
        "/devtickets-files/APP-1/",
        {"file": [SimpleUploadedFile("shot.png", PNG, "image/png"),
                  SimpleUploadedFile("notes.html", b"<script>x</script>", "text/html")]},
        headers=csrf_header(client),
    )  # fmt: skip
    assert made.status_code == 201, made.content
    png, html = made.json()["ids"]
    assert TicketAttachment.objects.get(pk=png).uploaded_by.email == "sam@example.com"

    shown = client.get(f"/devtickets-files/attachment/{png}/")
    assert shown.status_code == 200 and shown["Content-Type"] == "image/png"
    assert b"".join(shown.streaming_content) == PNG
    saved = client.get(f"/devtickets-files/attachment/{html}/")
    assert saved["Content-Type"] == "application/octet-stream"
    assert saved["Content-Disposition"].startswith("attachment")
    assert saved["X-Content-Type-Options"] == "nosniff"

    # Too large is refused here, before anything is sent.
    calls = len(as_client.calls)
    settings.DEV_TICKETS = {**settings.DEV_TICKETS, "MAX_ATTACHMENT_MB": 0}
    big = client.post(
        "/devtickets-files/APP-1/", {"file": SimpleUploadedFile("big.png", PNG, "image/png")},
        headers=csrf_header(client),
    )  # fmt: skip
    assert big.status_code == 400 and "too large" in big.json()["problems"][0]
    assert len(as_client.calls) == calls


def test_a_client_sends_no_mail_hands_out_no_keys_and_serves_no_assistant(as_client):
    out = StringIO()
    call_command("devtickets_notify", stdout=out)
    assert "hub sends the mail" in out.getvalue()
    with pytest.raises(CommandError, match="hub"):
        call_command("devtickets_client", "list")
    with pytest.raises(ImproperlyConfigured, match="hub"):
        register_tools(lambda *a: None)

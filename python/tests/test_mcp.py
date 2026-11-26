"""The assistant tools, registered the way a host's MCP server would take them."""

import pytest
from django.core.exceptions import PermissionDenied

from dev_tickets import people, service
from dev_tickets.mcp import TOOLS, register_tools
from dev_tickets.models import TicketNotification

pytestmark = pytest.mark.django_db


@pytest.fixture
def server():
    tools = {}

    def register(name, description, schema, handler):
        assert schema["type"] == "object" and set(schema["required"]) <= set(schema["properties"])
        tools[name] = handler

    names = register_tools(register)
    assert names == [f"tickets_{t.name}" for t in TOOLS]
    return tools


def test_every_tool_is_registered_with_the_prefix(server):
    assert set(server) == {
        "tickets_team", "tickets_list", "tickets_get", "tickets_create", "tickets_update",
        "tickets_comment", "tickets_link", "tickets_unlink",
    }  # fmt: skip


def test_outsiders_get_nothing_from_any_tool(server, outsider, lead):
    ticket = service.create_ticket(user=lead, title="Secret")
    with pytest.raises(PermissionDenied):
        server["tickets_list"](outsider)
    with pytest.raises(PermissionDenied):
        server["tickets_get"](outsider, ticket=ticket.identifier)
    with pytest.raises(PermissionDenied):
        server["tickets_create"](outsider, title="Sneaky")


def test_an_assistant_files_and_updates_like_a_person_and_people_hear(server, lead, dev):
    made = server["tickets_create"](
        dev, title="Clock photo blurry", labels=["Bug"], assignee="Maya Okafor", priority=2
    )
    assert made["ticket"] == "APP-1" and made["reporter"] == "Sam"
    assert made["labels"] == ["Bug"] and made["priority"] == "High"

    updated = server["tickets_update"](dev, ticket="APP-1", state="in_progress", assignee="none")
    assert updated["state"] == "in_progress" and updated["assignee"] is None
    # The assignee was told about the filing and the moves, as with any change.
    assert TicketNotification.objects.filter(person=people.for_user(lead)).count() == 3


def test_refusals_are_worded_for_the_model(server, lead):
    service.create_ticket(user=lead, title="x")
    with pytest.raises(service.TicketError, match="Unknown state"):
        server["tickets_update"](lead, ticket="APP-1", state="nonsense")
    with pytest.raises(service.TicketError, match="Unknown label"):
        server["tickets_create"](lead, title="y", labels=["Nope"])
    with pytest.raises(service.TicketError, match="No ticket"):
        server["tickets_get"](lead, ticket="APP-99")
    with pytest.raises(service.TicketError, match="not linked"):
        service.create_ticket(user=lead, title="z")
        server["tickets_unlink"](lead, ticket="APP-1", other="APP-2")


def test_list_hides_closed_tickets_unless_asked(server, lead):
    service.create_ticket(user=lead, title="Open bug")
    service.create_ticket(user=lead, title="Old bug", state="done")
    assert [t["title"] for t in server["tickets_list"](lead, search="bug")["tickets"]] == [
        "Open bug"
    ]
    everything = server["tickets_list"](lead, search="bug", include_closed=True)
    assert everything["count"] == 2


def test_link_comment_and_unlink_round_trip(server, lead):
    service.create_ticket(user=lead, title="One")
    service.create_ticket(user=lead, title="Two")
    linked = server["tickets_link"](lead, ticket="APP-1", other="APP-2", kind="blocks")
    assert linked["links"] == [
        {"kind": "blocks", "direction": "out", "ticket": "APP-2", "title": "Two"}
    ]
    commented = server["tickets_comment"](lead, ticket="APP-2", body="Waiting on APP-1")
    assert commented["comments"][0]["body"] == "Waiting on APP-1"
    assert server["tickets_unlink"](lead, ticket="APP-2", other="APP-1")["links"] == []
    assert server["tickets_team"](lead)["prefix"] == "APP"

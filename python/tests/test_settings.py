"""The Settings dialog: lanes are data the team edits, and the mode and hub connection
can be set without touching the host's settings."""

import json

import pytest

from dev_tickets import client, conf, lanes, service, states
from dev_tickets.models import TicketEvent, TicketState, TrackerSettings
from dev_tickets.service import TicketError
from tests.conftest import browser, csrf_header, gql
from tests.hubtools import actor, api_gql

pytestmark = pytest.mark.django_db


def file(user, title="Something broke", **kw):
    return service.create_ticket(user=user, title=title, **kw)


# --- lanes ------------------------------------------------------------------------


def test_a_new_lane_goes_last_and_a_rename_moves_no_ticket(lead):
    review = lanes.save_lane(key=None, name="In Review", type="started")
    assert [s.name for s in states.board_states()][-1] == "In Review"
    ticket = file(lead, state=review.key)

    lanes.save_lane(key=review.key, name="Code review", type="started")
    ticket.refresh_from_db()
    assert ticket.state == review.key and ticket.state_name == "Code review"


def test_new_tickets_land_in_whatever_lane_is_first(lead):
    keys = [s.key for s in states.all_states()]
    lanes.reorder_lanes([states.BACKLOG] + [k for k in keys if k != states.BACKLOG])
    assert file(lead).state == states.BACKLOG
    with pytest.raises(TicketError, match="every lane once"):
        lanes.reorder_lanes([states.BACKLOG])


def test_retyping_a_lane_opens_or_closes_the_tickets_in_it(lead):
    review = lanes.save_lane(key=None, name="Shipped", type="started")
    ticket = file(lead, state=review.key)
    assert not ticket.is_closed and ticket.closed_at is None

    lanes.save_lane(key=review.key, name="Shipped", type="completed")
    ticket.refresh_from_db()
    assert ticket.is_closed and ticket.closed_at is not None

    lanes.save_lane(key=review.key, name="Shipped", type="started")
    ticket.refresh_from_db()
    assert ticket.closed_at is None


def test_removing_a_lane_with_tickets_needs_somewhere_to_put_them(lead):
    review = lanes.save_lane(key=None, name="Review", type="started")
    ticket = file(lead, state=review.key)
    with pytest.raises(TicketError, match="still holds 1 ticket"):
        lanes.delete_lane(review.key, move_to=None)

    assert lanes.delete_lane(review.key, move_to=states.DONE) == 1
    ticket.refresh_from_db()
    assert ticket.state == states.DONE and ticket.closed_at is not None
    moved = TicketEvent.objects.get(ticket=ticket, kind=TicketEvent.Kind.STATE)
    assert (moved.old, moved.new) == ("Review", "Done")
    assert not TicketState.objects.filter(key=review.key).exists()


def test_the_board_always_keeps_a_lane(lead):
    on_board = list(TicketState.objects.filter(on_board=True))
    for lane in on_board[1:]:
        lanes.delete_lane(lane.key, move_to=on_board[0].key)
    with pytest.raises(TicketError, match="at least one lane"):
        lanes.delete_lane(on_board[0].key, move_to=states.CANCELED)
    with pytest.raises(TicketError, match="at least one lane"):
        lanes.save_lane(key=on_board[0].key, name=on_board[0].name, type="triage", on_board=False)


def test_a_duplicate_goes_to_whichever_lane_is_of_the_duplicate_type(lead):
    TicketState.objects.filter(key=states.DUPLICATE).update(name="Dupe", key="dupe")
    states.clear_cache()
    a, b = file(lead, "A"), file(lead, "B")
    service.add_relation(a, lead, b, states.DUPLICATE_OF)
    a.refresh_from_db()
    assert a.state == "dupe" and a.is_closed


def test_lanes_are_edited_over_graphql_and_counted(lead):
    c = browser(lead)
    made = gql(c, 'mutation { saveDevTicketLane(name: "QA", type: "started") { id name } }')
    key = made["data"]["saveDevTicketLane"]["id"]
    file(lead, state=key)
    rows = gql(c, "{ devTicketLanes { id name tickets } }")["data"]["devTicketLanes"]
    assert {"id": key, "name": "QA", "tickets": 1} in rows
    refused = gql(c, f'mutation {{ deleteDevTicketLane(id: "{key}") }}')
    assert "choose a lane" in refused["errors"][0]["message"]


# --- the connection ---------------------------------------------------------------


def post(c, path, data=None):
    return c.post(
        f"/devtickets/settings/{path}", data=json.dumps(data or {}),
        content_type="application/json", headers=csrf_header(c),
    )  # fmt: skip


def test_only_people_who_may_configure_reach_the_connection(lead, outsider, settings):
    assert browser(outsider).get("/devtickets/settings/").status_code == 403
    settings.DEV_TICKETS = {**settings.DEV_TICKETS, "CAN_CONFIGURE": lambda u: False}
    assert browser(lead).get("/devtickets/settings/").status_code == 403


def test_the_mode_can_be_set_here_unless_the_host_fixes_it(lead, settings):
    c = browser(lead)
    state = post(c, "connection/", {"mode": "hub"}).json()
    assert state["mode"] == "hub" and conf.mode() == "hub"
    assert TrackerSettings.load().mode == "hub"

    settings.DEV_TICKETS = {**settings.DEV_TICKETS, "MODE": "standalone"}
    conf.clear_cache()
    refused = post(c, "connection/", {"mode": "hub"})
    assert refused.status_code == 400 and conf.mode() == "standalone"
    assert browser(lead).get("/devtickets/settings/").json()["locked"]["mode"] is True


def test_a_client_connection_is_tried_before_it_is_saved(lead, monkeypatch):
    answers = iter([{"ok": False, "message": "That hub API key is not valid."},
                    {"ok": True, "team": "Acme", "prefix": "ACME"}])  # fmt: skip
    tried = []
    monkeypatch.setattr(
        client, "probe", lambda req, url, key: tried.append((url, key)) or next(answers)
    )
    c = browser(lead)
    data = {
        "mode": "client", "hubUrl": "https://hub.example.com", "hubApiKey": "dt_x",
        "source": "staging",
    }  # fmt: skip

    refused = post(c, "connection/", data)
    assert refused.status_code == 400 and "not valid" in refused.json()["message"]
    assert conf.mode() == "standalone"

    saved = post(c, "connection/", data).json()
    assert saved["mode"] == "client" and saved["hasKey"] and "dt_x" not in json.dumps(saved)
    assert (conf.get("HUB_URL"), conf.get("HUB_API_KEY")) == ("https://hub.example.com", "dt_x")
    assert tried == [("https://hub.example.com", "dt_x")] * 2


def test_a_hub_hands_out_keys_that_work_until_revoked(lead):
    c = browser(lead)
    assert post(c, "clients/", {"name": "staging"}).status_code == 400  # not a hub yet
    post(c, "connection/", {"mode": "hub"})

    made = post(c, "clients/", {"name": "staging", "readOnly": False}).json()
    key = made["key"]
    assert key.startswith("dt_") and made["clients"][0]["keyPrefix"] == key[:8]
    assert "key" not in browser(lead).get("/devtickets/settings/").json()  # shown once
    answer = api_gql(key, "{ devSupportConfig { prefix } }", who=actor())
    assert answer["data"]["devSupportConfig"]["prefix"] == "APP"

    post(c, f"clients/{made['clients'][0]['id']}/", {"revoke": True})
    assert api_gql(key, "{ devSupportConfig { prefix } }", who=actor(), status=401)["errors"]


def test_assistant_tools_refuse_once_settings_make_this_a_client(lead):
    from dev_tickets.mcp import register_tools

    tools = {}
    register_tools(lambda name, _d, _s, handler: tools.__setitem__(name, handler))
    assert tools["tickets_team"](lead)["states"]
    row = TrackerSettings.load()
    row.mode, row.hub_url, row.hub_api_key, row.source = "client", "https://hub", "k", "x"
    row.save()
    conf.clear_cache()
    with pytest.raises(TicketError, match="hub"):
        tools["tickets_team"](lead)

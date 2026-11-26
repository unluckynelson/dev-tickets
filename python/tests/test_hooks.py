"""The settings a host app plugs in: access, team, context, titles, prefix, mode."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured

from dev_tickets import conf, service, states, titles
from dev_tickets.models import DevTicket
from tests.conftest import browser, gql

pytestmark = pytest.mark.django_db

User = get_user_model()

CONFIG = (
    "{ devSupportConfig { enabled prefix boardUrl teamName "
    "assignees { name } labels { name } } }"
)


def with_settings(settings, **values):
    settings.DEV_TICKETS = {**settings.DEV_TICKETS, **values}


def test_config_says_disabled_rather_than_failing_for_outsiders(outsider, lead):
    for client in (browser(), browser(outsider)):
        result = gql(client, CONFIG)
        assert "errors" not in result
        config = result["data"]["devSupportConfig"]
        assert config["enabled"] is False
        assert config["assignees"] == [] and config["labels"] == []
        assert config["prefix"] == "APP"

    config = gql(browser(lead), CONFIG)["data"]["devSupportConfig"]
    assert config["enabled"] is True
    assert config["boardUrl"] == "https://app.example.com/admin/dev-tickets"
    assert config["assignees"] == [{"name": "Maya Okafor"}]
    assert [lbl["name"] for lbl in config["labels"]] == ["Bug", "Feature", "Improvement"]


def test_can_access_decides_who_is_in(settings, outsider, lead):
    with_settings(settings, CAN_ACCESS=lambda user: user.username == "outsider")
    assert gql(browser(outsider), CONFIG)["data"]["devSupportConfig"]["enabled"] is True
    assert gql(browser(lead), "{ devTicketBoard { teamName } }")["errors"]
    made = gql(browser(outsider), 'mutation { createDevTicket(title: "In") { reporterName } }')
    assert made["data"]["createDevTicket"]["reporterName"] == "outsider"


def test_can_access_is_never_asked_about_an_anonymous_user(settings):
    asked = []
    with_settings(settings, CAN_ACCESS=lambda user: asked.append(user) or True)
    assert gql(browser(), "{ devTicketBoard { teamName } }")["errors"]
    assert asked == []


def test_the_team_hook_decides_who_can_be_assigned(settings, lead, outsider):
    with_settings(settings, TEAM="tests.test_hooks.everyone")
    ticket = service.create_ticket(user=lead, title="x")
    done = gql(
        browser(lead),
        "mutation($id: String!, $a: String) { assignDevTicket(id: $id, assigneeId: $a) "
        "{ assigneeName } }",
        {"id": ticket.identifier, "a": str(outsider.pk)},
    )
    assert done["data"]["assignDevTicket"]["assigneeName"] == "outsider"


def everyone():
    return User.objects.all()


def test_context_label_records_where_a_ticket_was_filed_from(settings, lead):
    with_settings(settings, CONTEXT_LABEL=lambda request: f"Workspace of {request.user}")
    made = gql(browser(lead), 'mutation { createDevTicket(title: "x") { contextLabel } }')
    assert made["data"]["createDevTicket"]["contextLabel"] == "Workspace of lead"


DESCRIBE = "mutation($d: String!) { createDevTicket(description: $d) { title } }"


def test_a_blank_title_comes_from_the_title_generator(settings, lead):
    seen = []

    def generate(description, request):
        seen.append(request.user.username)
        return '"Export: Safari downloads nothing."\nextra line'

    with_settings(settings, TITLE_GENERATOR=generate)
    made = gql(browser(lead), DESCRIBE, {"d": "Clicking export in Safari does nothing"})
    assert made["data"]["createDevTicket"]["title"] == "Export: Safari downloads nothing"
    assert seen == ["lead"]


@pytest.mark.parametrize("generate", [None, lambda d, r: "", lambda d, r: 1 / 0])
def test_without_a_usable_title_the_first_line_stands_in(settings, lead, generate):
    with_settings(settings, TITLE_GENERATOR=generate)
    long = "When you add a person to the schedule who is not rostered nothing happens " * 2
    made = gql(browser(lead), DESCRIBE, {"d": f"\n{long}\nsecond line"})
    title = made["data"]["createDevTicket"]["title"]
    assert title.startswith("When you add a person") and title.endswith("…") and len(title) <= 71


def test_no_title_and_no_description_is_refused(lead):
    assert gql(browser(lead), DESCRIBE, {"d": "  "})["errors"]
    assert not DevTicket.objects.exists()


def test_first_line_skips_blank_lines():
    assert titles.first_line("\n\n  Totals wrong  \nmore") == "Totals wrong"


def test_the_prefix_names_and_finds_tickets(settings, lead):
    ticket = service.create_ticket(user=lead, title="x")
    assert ticket.identifier == "APP-1"
    for ref in ("APP-1", "app-1", "1", " APP-1 "):
        assert service.find_ticket(ref) == ticket
    assert service.find_ticket("OTHER-1") is None

    with_settings(settings, PREFIX="mhq")
    assert ticket.identifier == "MHQ-1"
    assert states.parse_identifier("MHQ-1") == 1 and states.parse_identifier("APP-1") is None


def test_only_standalone_mode_is_built_and_unknown_settings_are_caught(settings):
    for mode in ("hub", "client"):
        with_settings(settings, MODE=mode)
        with pytest.raises(ImproperlyConfigured, match="not implemented"):
            conf.check()
    settings.DEV_TICKETS = {"PREFX": "x"}
    with pytest.raises(ImproperlyConfigured, match="PREFX"):
        conf.check()


def test_a_bad_dotted_path_names_the_setting(settings, lead):
    with_settings(settings, CAN_ACCESS="nowhere.at_all")
    with pytest.raises(ImproperlyConfigured, match="CAN_ACCESS"):
        conf.hook("CAN_ACCESS")

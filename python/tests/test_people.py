"""People: who someone is, whichever way they arrive."""

import pytest
from django.contrib.auth import get_user_model

from dev_tickets import people, service
from dev_tickets.models import Person

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_a_remote_person_is_linked_when_the_same_email_signs_in_here(db):
    remote = people.for_remote("Priya@Example.com", name="Priya S", team=True)
    assert remote.email == "priya@example.com" and remote.user is None

    user = User.objects.create_user(
        "priya", email="PRIYA@example.com", first_name="Priya", last_name="Shah"
    )
    local = people.for_user(user)
    assert local.pk == remote.pk
    assert (local.user, local.name) == (user, "Priya Shah")
    # She is not a superuser here, so the TEAM hook, not the client, now decides.
    assert local.is_team is False
    # A client still naming her by her old name changes nothing it does not own.
    people.for_remote("priya@example.com", name="P. Shah", team=True)
    local.refresh_from_db()
    assert (local.name, local.is_team) == ("Priya Shah", False)


def test_two_local_users_sharing_an_address_stay_two_people(db):
    a = User.objects.create_user("a", email="shared@example.com")
    b = User.objects.create_user("b", email="shared@example.com")
    pa, pb = people.for_user(a), people.for_user(b)
    assert pa.pk != pb.pk
    assert (pa.email, pb.email) == ("shared@example.com", None)
    assert Person.objects.count() == 2


def test_the_team_follows_the_hook_and_the_default_assignee_matches_a_username(settings, lead):
    remote = people.for_remote("contractor@example.com", name="Jo Contractor", team=True)
    people.for_remote("visitor@example.com", name="Vee Visitor", team=False)
    names = [p.display_name for p in service.team_members()]
    assert names == ["Jo Contractor", "Maya Okafor"]

    settings.DEV_TICKETS = {**settings.DEV_TICKETS, "DEFAULT_ASSIGNEE": "lead"}
    assert service.default_assignee().user == lead
    settings.DEV_TICKETS = {**settings.DEV_TICKETS, "DEFAULT_ASSIGNEE": "contractor@example.com"}
    assert service.default_assignee() == remote

    lead.is_superuser = False
    lead.save()
    assert [p.display_name for p in service.team_members()] == ["Jo Contractor"]

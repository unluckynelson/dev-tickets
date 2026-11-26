import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()

PNG = (  # 1x1 PNG
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
    b"\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def browser(user=None) -> Client:
    """A client that enforces CSRF, as a browser meets it, holding the cookie."""
    client = Client(enforce_csrf_checks=True)
    if user is not None:
        client.force_login(user)
    response = client.get("/devtickets/csrf/")
    assert response.status_code == 204
    return client


def csrf_header(client: Client) -> dict:
    return {"x-csrftoken": client.cookies["csrftoken"].value}


def gql(client: Client, query: str, variables: dict | None = None) -> dict:
    response = client.post(
        "/devtickets/graphql/",
        data=json.dumps({"query": query, "variables": variables or {}}),
        content_type="application/json",
        headers=csrf_header(client),
    )
    assert response.status_code == 200, response.content
    return response.json()


@pytest.fixture
def lead(db):
    return User.objects.create_superuser(
        "lead", email="lead@example.com", password="x", first_name="Maya", last_name="Okafor"
    )


@pytest.fixture
def dev(db):
    return User.objects.create_superuser(
        "sam", email="sam@example.com", password="x", first_name="Sam"
    )


@pytest.fixture
def outsider(db):
    return User.objects.create_user("outsider", email="out@example.com", password="x")


@pytest.fixture(autouse=True)
def _fresh_caches():
    """Lanes and stored settings are cached for a request; a test's rollback fires no
    signal, so start every test from the database."""
    from dev_tickets import conf, states

    states.clear_cache()
    conf.clear_cache()
    yield
    states.clear_cache()
    conf.clear_cache()

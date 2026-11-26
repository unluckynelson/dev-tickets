"""`manage.py devtickets_client`: the keys a hub hands to other installs."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from dev_tickets import hub
from dev_tickets.models import HubClient

pytestmark = pytest.mark.django_db


def run(*args) -> str:
    out = StringIO()
    call_command("devtickets_client", *args, stdout=out)
    return out.getvalue()


def test_add_list_rotate_and_revoke():
    shown = run("add", "staging", "--source", "stage", "--read-only")
    key = shown.strip().splitlines()[-1]
    row = HubClient.objects.get()
    assert key.startswith("dt_") and len(key) > 40
    assert (row.source, row.read_only, row.key_prefix) == ("stage", True, key[:8])
    assert row.key_hash == hub.hash_key(key) and key not in row.key_hash

    with pytest.raises(CommandError, match="already"):
        run("add", "staging")
    listed = run("list")
    assert "staging" in listed and key[:8] in listed and key not in listed

    new = run("rotate", "staging").strip().splitlines()[-1]
    row.refresh_from_db()
    assert new != key and row.key_hash == hub.hash_key(new)

    run("revoke", "staging")
    row.refresh_from_db()
    assert row.revoked_at is not None and "REVOKED" in run("list")
    with pytest.raises(CommandError, match="No client"):
        run("revoke", "production")

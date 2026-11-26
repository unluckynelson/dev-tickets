"""Registering the assistant tools happens when the host imports its MCP module, often
before any database is reachable (a test run collecting, a server starting). No
django_db mark here on purpose: pytest-django fails any query this makes."""

from dev_tickets.mcp import register_tools


def test_registering_assistant_tools_needs_no_database():
    assert len(register_tools(lambda *a: None)) == 8

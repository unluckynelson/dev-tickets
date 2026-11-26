"""The one access check, used by GraphQL, the file views and the MCP tools."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied

from . import conf


def can_access(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(conf.hook("CAN_ACCESS")(user))


def access_required(user):
    """The user, or PermissionDenied: for anyone signed out or outside the team."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")
    if not can_access(user):
        raise PermissionDenied("You do not have access to dev tickets.")
    return user


def context_label(request) -> str:
    hook = conf.hook("CONTEXT_LABEL")
    if hook is None or request is None:
        return ""
    return str(hook(request) or "")[:150]

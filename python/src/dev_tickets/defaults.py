"""The hooks' default implementations, named by dotted path in `conf.DEFAULTS`."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives


def can_access(user) -> bool:
    """Active superusers only: tickets carry screenshots of whatever a user had open."""
    return bool(getattr(user, "is_authenticated", False) and user.is_active and user.is_superuser)


def team():
    return get_user_model().objects.filter(is_active=True, is_superuser=True)


def send_mail(subject: str, text: str, html: str, to: list[str]) -> None:
    """One multipart message: the text half is what spam filters and plain-text
    clients read, so an HTML-only digest is never sent."""
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, to)
    message.attach_alternative(html, "text/html")
    message.send()

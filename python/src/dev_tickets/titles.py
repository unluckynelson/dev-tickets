"""A ticket's title written from its description.

Asking for a title and a description gets the same thing written twice, or a vague
one-word title. So the widget can leave the title out, and `TITLE_GENERATOR` -- a
host hook, typically an LLM call -- writes one. Every way that can fail (no hook,
an exception, an empty answer) falls back to the description's first line, so
filing a ticket never fails over a title.
"""

from __future__ import annotations

import logging

from . import conf

log = logging.getLogger(__name__)

FALLBACK_LENGTH = 70
MAX_TITLE = 120


def first_line(description: str) -> str:
    """The description's first non-blank line, cut at a word to fit a title."""
    line = next((ln.strip() for ln in description.splitlines() if ln.strip()), "")
    if len(line) <= FALLBACK_LENGTH:
        return line
    return line[:FALLBACK_LENGTH].rsplit(" ", 1)[0] + "…"


def title_for(description: str, request=None) -> str:
    fallback = first_line(description) or "Untitled"
    generate = conf.hook("TITLE_GENERATOR")
    if generate is None:
        return fallback
    try:
        answer = generate(description, request)
    except Exception:  # a title is a nicety; never fail a ticket over one
        log.exception("TITLE_GENERATOR failed")
        return fallback
    # Models wrap a title in quotes, end it with a full stop and add a line of chat.
    lines = [ln.strip() for ln in str(answer or "").splitlines() if ln.strip()]
    title = lines[0].strip("\"'“”").rstrip(".").strip()[:MAX_TITLE] if lines else ""
    return title or fallback

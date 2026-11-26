"""What the digest email says about each ticket.

The bell shows one short line per change (`notify.summary`); the email is read
away from the app, so it carries the whole ticket: its state, priority, people and
labels, the description, and every comment in full -- cutting a comment short
leaves people opening the app to read the rest of a sentence.

Markdown is rendered and then cleaned to a small set of tags with nothing but
links allowed out, because ticket text is typed by people and lands in an inbox.
Email clients drop `<style>`, so each tag gets its look inline here.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import markdown as markdown_lib
import nh3
from django.utils.safestring import SafeString, mark_safe

from . import conf, states
from .models import TicketEvent

Kind = TicketEvent.Kind

_TAGS = {"p", "br", "strong", "em", "code", "pre", "ul", "ol", "li", "blockquote", "a",
         "h1", "h2", "h3", "h4", "hr", "table", "thead", "tbody", "tr", "th", "td"}  # fmt: skip
_STYLE = {
    "p": "margin:0 0 10px 0;",
    "ul": "margin:0 0 10px 0;padding-left:22px;",
    "ol": "margin:0 0 10px 0;padding-left:22px;",
    "li": "margin:0 0 4px 0;",
    "code": "font-family:Consolas,Menlo,monospace;font-size:13px;background:#f1f4f9;"
    "padding:1px 4px;border-radius:3px;",
    "pre": "margin:0 0 10px 0;padding:10px;background:#f1f4f9;border-radius:6px;"
    "white-space:pre-wrap;font-size:13px;",
    "blockquote": "margin:0 0 10px 0;padding-left:10px;border-left:3px solid #d1d9e6;"
    "color:#4b5563;",
    "a": "color:#0a5fd4;",
    "h1": "margin:0 0 8px 0;font-size:16px;",
    "h2": "margin:0 0 8px 0;font-size:15px;",
    "h3": "margin:0 0 8px 0;font-size:14px;",
    "h4": "margin:0 0 8px 0;font-size:14px;",
    "table": "border-collapse:collapse;margin:0 0 10px 0;",
    "th": "border:1px solid #d1d9e6;padding:4px 8px;text-align:left;",
    "td": "border:1px solid #d1d9e6;padding:4px 8px;",
}
_OPEN_TAG = re.compile(r"<({})(\s[^>]*)?>".format("|".join(_STYLE)))


def board_url() -> str:
    return str(conf.get("BOARD_URL") or "").rstrip("/")


def _site() -> str:
    """Scheme and host of the board, for making in-app links absolute."""
    parts = urlsplit(board_url())
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def ticket_url(identifier: str) -> str:
    base = board_url()
    return f"{base}/{identifier}" if base else ""


def markdown_html(source: str) -> SafeString:
    """Ticket markdown as email-safe HTML, links made absolute, styles inline."""
    rendered = markdown_lib.markdown(source or "", extensions=["tables", "sane_lists"])
    clean = nh3.clean(
        rendered, tags=_TAGS, attributes={"a": {"href"}}, url_schemes={"http", "https", "mailto"},
        link_rel="noopener",
    )  # fmt: skip
    # An in-app link ("/settings") means nothing in an inbox.
    site = _site()
    if site:
        clean = re.sub(r'href="/(?!/)', f'href="{site}/', clean)
    else:
        clean = re.sub(r'\shref="/(?!/)[^"]*"', "", clean)
    return mark_safe(_OPEN_TAG.sub(lambda m: f'<{m[1]}{m[2] or ""} style="{_STYLE[m[1]]}">', clean))


def _name(user) -> str:
    return (user.get_full_name() or user.get_username()) if user else ""


def _change(event: TicketEvent) -> dict:
    """One change: the line the bell shows, and for a comment its full text."""
    from .notify import summary

    if event.kind == Kind.COMMENT:
        body = event.comment.body if event.comment_id else event.new
        return {"line": f"{_name(event.actor) or 'Someone'} commented", "body": markdown_html(body),
                "text": body}  # fmt: skip
    return {"line": summary(event), "body": None, "text": ""}


def items(rows) -> list[dict]:
    """One entry per ticket, oldest change first within each."""
    grouped: dict = {}
    for n in rows:
        t = n.event.ticket
        if t.pk not in grouped:
            grouped[t.pk] = {
                "identifier": t.identifier,
                "title": t.title,
                "url": ticket_url(t.identifier),
                "facts": [
                    ("State", t.state_name),
                    ("Priority", states.PRIORITY_LABELS.get(t.priority, "")),
                    ("Assignee", _name(t.assignee) or "Unassigned"),
                    ("Reported by", _name(t.reported_by)),
                    ("Labels", ", ".join(lb.name for lb in t.labels.all())),
                    ("Filed from", t.context_label),
                    ("Page", t.page_url),
                ],
                "description": markdown_html(t.description) if t.description.strip() else None,
                "description_text": t.description.strip(),
                "changes": [],
            }
        grouped[t.pk]["changes"].append(_change(n.event))
    for entry in grouped.values():
        entry["facts"] = [(k, v) for k, v in entry["facts"] if v]
    return list(grouped.values())

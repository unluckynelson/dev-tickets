"""Playground settings. Not for production: DEBUG on, SQLite, mail printed to the console.

The Nuxt playground proxies /devtickets/, /devtickets-files/ and /playground/ to this
server, so the browser sees one origin and no CORS settings are needed. Sign in at
http://localhost:3300/playground/ by picking a person.

One project, two roles, picked by `DEV_TICKETS_MODE`:

- unset or "hub": the hub on :8300, `playground.sqlite3`, Nuxt on :3300.
- "client": a client on :8301 (`./playground/run.sh --client`), `playground-client.sqlite3`,
  Nuxt on :3301, forwarding to the hub with the key in `DEV_TICKETS_HUB_KEY`.
- "open": an install whose mode and hub are left to the board's Settings → Connection
  (`./playground/run.sh --open`): :8302, `playground-open.sqlite3`, Nuxt on :3302.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODE = os.environ.get("DEV_TICKETS_MODE", "hub")
CLIENT = MODE == "client"
OPEN = MODE == "open"
ROLE = "client" if CLIENT else "open" if OPEN else ""  # names its database, media, cookie
WEB = {"client": "http://localhost:3301", "open": "http://localhost:3302"}.get(ROLE, "http://localhost:3300")

SECRET_KEY = "playground-not-secret"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = [WEB, WEB.replace("localhost", "127.0.0.1")]
# Browsers do not keep cookies apart by port, so the client's session needs a name of
# its own or signing in on :3301 would sign you out on :3300. The CSRF cookie may be
# shared: either server accepts any well-formed token.
SESSION_COOKIE_NAME = f"{ROLE}_sessionid" if ROLE else "sessionid"
USE_TZ = True
TIME_ZONE = "UTC"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "dev_tickets",
    "playground",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
ROOT_URLCONF = "playground.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / (f"playground-{ROLE}.sqlite3" if ROLE else "playground.sqlite3"),
    }
}
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": BASE_DIR / (f"media-{ROLE}" if ROLE else "media")},
    },
}
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "tickets@example.com"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEV_TICKETS = {
    "PREFIX": "APP",
    "BOARD_URL": "http://localhost:3300/admin/dev-tickets",
    "CONTEXT_LABEL": "playground.hooks.context_label",
}
if not OPEN:
    DEV_TICKETS["MODE"] = MODE
if OPEN:
    DEV_TICKETS["AVATAR"] = "playground.hooks.avatar"
if CLIENT:
    DEV_TICKETS |= {
        "HUB_URL": "http://localhost:8300",
        "HUB_API_KEY": os.environ.get("DEV_TICKETS_HUB_KEY", ""),
        "SOURCE": "client-demo",
        "AVATAR": "playground.hooks.avatar",
    }

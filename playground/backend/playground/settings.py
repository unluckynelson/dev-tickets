"""Playground settings. Not for production: DEBUG on, SQLite, mail printed to the console.

The Nuxt playground proxies /devtickets/, /devtickets-files/ and /playground/ to this
server, so the browser sees one origin and no CORS settings are needed. Sign in at
http://localhost:3300/playground/ by picking a person.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "playground-not-secret"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:3300", "http://127.0.0.1:3300"]
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
        "NAME": BASE_DIR / "playground.sqlite3",
    }
}
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": BASE_DIR / "media"},
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

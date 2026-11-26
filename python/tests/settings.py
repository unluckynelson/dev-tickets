"""A minimal host project for the tests: SQLite, sessions, the locmem mail backend."""

import tempfile

SECRET_KEY = "dev-tickets-tests"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
USE_TZ = True
TIME_ZONE = "UTC"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "dev_tickets",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
ROOT_URLCONF = "tests.urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
TEMPLATES = [
    {"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True},
]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": tempfile.mkdtemp(prefix="dev-tickets-tests-")},
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "tickets@example.com"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEV_TICKETS = {
    "PREFIX": "APP",
    "BOARD_URL": "https://app.example.com/admin/dev-tickets",
    "DEFAULT_ASSIGNEE": "lead@example.com",
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests

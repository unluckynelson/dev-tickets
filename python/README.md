# django-dev-tickets

The Django half of [Dev Tickets](../README.md): models, service layer, its own GraphQL
endpoint, attachment views, the email digest and the MCP tool definitions. Setup and
settings are documented in the [root README](../README.md); this file is for working on
the package itself.

## Layout

```
src/dev_tickets/
├── conf.py          the DEV_TICKETS settings and their defaults
├── defaults.py      default hooks: CAN_ACCESS, TEAM, SEND_MAIL
├── states.py        states, priorities, relation kinds, the identifier prefix
├── models.py
├── service.py       every write goes through here
├── notify.py        the bell and the digest email
├── digest.py        what the email says about each ticket
├── titles.py        TITLE_GENERATOR with a first-line fallback
├── types.py / queries.py / mutations.py / schema.py   GraphQL at devtickets/graphql/
├── views.py / urls.py                                  csrf, uploads, serving files
├── mcp.py           framework-agnostic assistant tools + register_tools()
└── management/commands/devtickets_notify.py
```

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,mcp]"
.venv/bin/pytest          # SQLite, no services needed
.venv/bin/ruff check .
```

`tests/settings.py` is a minimal host project. HTTP and GraphQL tests use
`Client(enforce_csrf_checks=True)` and fetch the cookie from `devtickets/csrf/`, because
Django's default test client switches CSRF off and a suite can pass while every real
browser request is refused.

After changing a model:

```bash
.venv/bin/python -m django makemigrations dev_tickets --settings=tests.settings
```

After changing the GraphQL types, regenerate the schema the Nuxt layer is checked against:

```bash
DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python -c "import django; django.setup(); \
from dev_tickets.schema import schema; open('schema.graphql','w').write(schema.as_str() + '\n')"
```

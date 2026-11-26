# Changelog

All notable changes to `django-dev-tickets` and `nuxt-dev-tickets`, which are released
together under one version. The format follows [Keep a Changelog](https://keepachangelog.com);
versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

- `django-dev-tickets` 0.1.0 (`python/`): the dev-ticket app extracted from AutoRoster, with
  its own GraphQL endpoint (`/devtickets/graphql/`), file views, digest emails, MCP tool
  definitions and the `DEV_TICKETS` settings hooks. Standalone mode only.
- `nuxt-dev-tickets` 0.1.0 (`nuxt/`): the board, ticket dialog, report widget (with
  highlight on page) and notification bell as a Nuxt layer.
- Playground (`playground/run.sh`): both packages wired together with sample data.
- Hub and client modes: one board for every environment. A client forwards the same
  GraphQL schema to the hub's API (`/devtickets/api/v1/`) with a per-environment key and
  the acting person; tickets point at people matched by email, and record the source
  they came through. `devtickets_client` adds, lists, rotates and revokes keys.
  `./playground/run.sh --client` runs a hub and a client side by side.
- Release tooling: `scripts/release.sh`, `scripts/check-versions.sh`, CI on every push,
  and a tag-triggered workflow that publishes to PyPI and npm and makes the GitHub release.

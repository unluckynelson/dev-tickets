# Changelog

All notable changes to `django-dev-tickets` and `nuxt-dev-tickets`, which are released
together under one version. The format follows [Keep a Changelog](https://keepachangelog.com);
versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

- Settings on the board (a gear in its corner, or `?settings=<tab>`): lanes, labels,
  notifications and the connection, in one dialog. The Labels button and the bell's email
  switch moved into it.
- Lanes are data (`TicketState`): add, rename, retype, reorder, hide or remove them. A
  lane's type decides whether its tickets are closed. Migration `0003` creates the seven
  lanes there were, with their keys, so existing tickets keep their state.
- The mode, hub address, key and source can be set in Settings → Connection and are
  stored in the database (`TrackerSettings`); `DEV_TICKETS` still wins and shows as
  locked. A client connection is tried before it is saved. As a hub, keys for other
  environments are made, rotated and revoked there too. New `CAN_CONFIGURE` hook.
- Assistant tools are registered without touching the database (hosts register at import);
  a client mode chosen in Settings refuses them when they run.
- `./playground/run.sh --open`: a second install with no mode set, to try setting it up
  from Settings.

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
- Fixed for host apps that render on the server (found installing it in BuilderCheck): the
  board now renders in the browser only, so it no longer fails to hydrate, and the layer
  registers PrimeVue's `v-tooltip` itself, which went missing when installed from npm or git.
  A host's typecheck also passes over the layer now (`@types/turndown` is a dependency, and
  the API client no longer leans on the host's Nitro route types).
- Fixed for a layer Nuxt fetches itself (`extends: ['github:unluckynelson/dev-tickets/nuxt#<ref>']`,
  which is how an npm app installs it, since npm cannot install from a subfolder): the dev
  server auto-imported `DevTicketsError` into the file declaring it and the app failed to
  start. The class now lives in `app/lib/errors.ts`, imported by name.
- Release tooling: `scripts/release.sh`, `scripts/check-versions.sh`, CI on every push,
  and a tag-triggered workflow that publishes to PyPI and npm and makes the GitHub release.

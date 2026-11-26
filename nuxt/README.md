# nuxt-dev-tickets

The frontend half of [Dev Tickets](../README.md): a Nuxt 4 layer with the board, the
report widget and the notification bell. Using it in an app is covered in the main
README; this file is for working on the layer itself.

## Layout

```
nuxt/
├── nuxt.config.ts        the layer: PrimeVue module, primeicons, runtimeConfig defaults
├── app/
│   ├── components/       DevTicket* (auto-imported into the host)
│   ├── composables/      useDevTickets, useDevTicketsApi, useDevTicketFilters
│   └── lib/              types, helpers, markdown — imported by relative path,
│                         never auto-imported, so their plain names can't collide
│                         with the host's
└── .playground/          a minimal host app that extends `..`
```

Rules that keep the layer portable:

- **Relative imports only inside the layer.** In a layer, `~` resolves to the *host's*
  source directory.
- **No pages.** The host chooses the board's route and renders `<DevTicketBoard>` there.
- **Style with PrimeVue's `--p-*` tokens**, never colours or variables from a host app.
- **Everything asks the server.** The parts hide themselves when `devSupportConfig`
  answers `enabled: false`. Nothing reads the host's user or auth state.

## Public components

| Component | Props |
| --- | --- |
| `<DevTicketBoard>` | `base-path` (where the host mounted it; the segment after it is the open ticket), `title` |
| `<DevTicketWidget>` | `auto-title` (default `true`: description only, the server writes the title), `new-tab` |
| `<DevTicketBell>` | — (takes its colour from the header it sits in) |

The widget floats bottom-right. Move it with `--dev-tickets-fab-bottom` and
`--dev-tickets-fab-right`.

## Runtime config

```ts
runtimeConfig: {
  public: {
    devTickets: {
      endpoint: '/devtickets/graphql/',   // the backend's dev-tickets GraphQL endpoint
      csrfUrl: '',                        // blank: endpoint with graphql/ -> csrf/
      boardPath: '/admin/dev-tickets',    // where links from the widget and bell go
    },
  },
}
```

All three can be set from the environment as usual, e.g.
`NUXT_PUBLIC_DEV_TICKETS_ENDPOINT`.

**CSRF.** The client `GET`s `csrfUrl` once and sends the token back as `X-CSRFToken`.
It takes the token from a `{ "csrfToken": "…" }` reply when there is one, otherwise
from the `csrftoken` cookie. Reading the cookie only works when the page and the
backend share a hostname (ports may differ). A 403 fetches the token again and retries
once.

## Development

Needs Node 22+.

```bash
npm install
npm run dev          # the playground on http://localhost:3000
npm run build        # builds the playground
npm run typecheck
npm run lint
```

The playground expects a dev-tickets backend at `http://localhost:8300`. Its pages
must be on the same hostname (`localhost`) so the session and CSRF cookies are shared,
and the backend must allow the playground's origin in `CORS_ALLOWED_ORIGINS` and
`CSRF_TRUSTED_ORIGINS`.

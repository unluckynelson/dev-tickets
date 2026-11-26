/**
 * Raised for a GraphQL error from the dev-tickets backend. Kept out of `composables/`
 * and imported by name: a class declared in an auto-imported file is also offered as
 * an auto-import, and where the layer is fetched by Nuxt itself (`extends:
 * ['github:...']`, under node_modules/.c12) the dev server injected that import into
 * the declaring file, which then failed with "already declared".
 */
export class DevTicketsError extends Error {}

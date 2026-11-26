import Aura from '@primeuix/themes/aura'

// A host app in miniature, for developing the layer: it extends `..` exactly as a
// real app extends `nuxt-dev-tickets`, and points at a dev-tickets backend.
export default defineNuxtConfig({
  extends: ['..'],
  // A real host usually configures PrimeVue itself too; listing it here as well
  // proves the layer's own registration does not clash with it.
  modules: ['@primevue/nuxt-module'],
  ssr: false,
  // The playground's Django (playground/backend, :8300) is proxied, so the browser sees
  // one origin: the session and CSRF cookies just work and no CORS is needed. The
  // layer's default endpoint, /devtickets/graphql/, is then right as it stands.
  // /playground/ is the backend's pick-a-person sign-in page.
  routeRules: {
    '/devtickets/**': { proxy: 'http://localhost:8300/devtickets/**' },
    '/devtickets-files/**': { proxy: 'http://localhost:8300/devtickets-files/**' },
    '/playground/**': { proxy: 'http://localhost:8300/playground/**' },
  },
  compatibilityDate: '2026-11-01',
  primevue: {
    options: {
      theme: { preset: Aura, options: { darkModeSelector: '.app-dark' } },
    },
  },
})

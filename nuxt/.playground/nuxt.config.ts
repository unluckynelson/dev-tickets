import Aura from '@primeuix/themes/aura'

// Which playground backend to proxy to: 8300 is the hub, 8301 the client that
// `playground/run.sh --client` starts. A second dev server needs its own build dir.
// (Read through globalThis: the layer has no @types/node for `process`.)
const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env
const backendPort = env?.PLAYGROUND_BACKEND_PORT || '8300'
const backend = `http://localhost:${backendPort}`

// A host app in miniature, for developing the layer: it extends `..` exactly as a
// real app extends `nuxt-dev-tickets`, and points at a dev-tickets backend.
export default defineNuxtConfig({
  extends: ['..'],
  // A real host usually configures PrimeVue itself too; listing it here as well
  // proves the layer's own registration does not clash with it.
  modules: ['@primevue/nuxt-module'],
  ssr: false,
  buildDir: backendPort === '8300' ? '.nuxt' : `.nuxt-${backendPort}`,
  // The playground's Django (playground/backend, :8300 or :8301) is proxied, so the browser sees
  // one origin: the session and CSRF cookies just work and no CORS is needed. The
  // layer's default endpoint, /devtickets/graphql/, is then right as it stands.
  // /playground/ is the backend's pick-a-person sign-in page.
  routeRules: {
    '/devtickets/**': { proxy: `${backend}/devtickets/**` },
    '/devtickets-files/**': { proxy: `${backend}/devtickets-files/**` },
    '/playground/**': { proxy: `${backend}/playground/**` },
  },
  compatibilityDate: '2026-11-01',
  primevue: {
    options: {
      theme: { preset: Aura, options: { darkModeSelector: '.app-dark' } },
    },
  },
})

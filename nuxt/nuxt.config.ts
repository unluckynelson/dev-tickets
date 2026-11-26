// The dev-tickets Nuxt layer. A host app adds `extends: ['nuxt-dev-tickets']` and
// gets the DevTicket* components and the useDevTickets composables. It registers
// no pages: the host picks the board's route (see README).
export default defineNuxtConfig({
  // Components are styled with PrimeVue and its `--p-*` tokens; the host chooses
  // the theme in its own `primevue` options.
  modules: ['@primevue/nuxt-module'],

  css: ['primeicons/primeicons.css'],

  runtimeConfig: {
    public: {
      devTickets: {
        /** The backend's dev-tickets GraphQL endpoint. */
        endpoint: '/devtickets/graphql/',
        /** GET once for the CSRF cookie. Blank: the endpoint with graphql/ -> csrf/. */
        csrfUrl: '',
        /** Where the host mounted <DevTicketBoard>; links from the widget and bell go here. */
        boardPath: '/admin/dev-tickets',
      },
    },
  },
})

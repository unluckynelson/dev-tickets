// The components use PrimeVue's `v-tooltip`. The PrimeVue module registers directives by
// transforming templates, and installed from node_modules this layer's templates are not
// transformed, so the directive went missing in host apps. Register it here unless the host has.
import Tooltip from 'primevue/tooltip'

export default defineNuxtPlugin((nuxtApp) => {
  if (!nuxtApp.vueApp.directive('tooltip')) nuxtApp.vueApp.directive('tooltip', Tooltip)
})

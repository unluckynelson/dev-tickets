// @ts-check
import { createConfigForNuxt } from '@nuxt/eslint-config/flat'

// The same rules as the AutoRoster app this came from: Nuxt's Vue + TypeScript
// config with the stylistic set (no semicolons, single quotes, 2-space indent,
// trailing commas). Built from @nuxt/eslint-config directly, not the @nuxt/eslint
// module, so the layer does not hand that module to every host app.
export default createConfigForNuxt({
  features: { stylistic: true },
  dirs: { src: ['./app', './.playground/app'] },
}).override('nuxt/rules', {}).append({
  ignores: ['.playground/.nuxt/**', '.playground/.output/**', '.nuxt/**', '.output/**'],
}, {
  rules: {
    // PrimeVue components are auto-imported and single-word by design.
    'vue/multi-word-component-names': 'off',
    // Attribute-per-line and element-exploding rules are noise on short tags.
    'vue/max-attributes-per-line': 'off',
    'vue/singleline-html-element-content-newline': 'off',
    'vue/html-indent': 'off',
    'curly': ['error', 'multi-line'],
    '@stylistic/max-statements-per-line': ['error', { max: 3 }],
  },
})

const path = require('path')

module.exports = {
  root: true,
  env: {
    node: true,
    browser: true
  },
  extends: [
    'plugin:vue/vue3-recommended',
    '@vue/standard'
  ],
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@babel/eslint-parser',
    requireConfigFile: false,
    ecmaVersion: 'latest',
    sourceType: 'module',
    babelOptions: {
      babelrc: false,
      configFile: false
    }
  },
  plugins: [
    'babel'
  ],
  globals: {
    localStorage: false,
    $: 'readonly',
    $$: 'readonly'
  },
  rules: {
    'arrow-parens': 0,
    'generator-star-spacing': 0,
    'no-tabs': 0,
    'comma-dangle': 0,
    'no-return-assign': 0,
  'object-curly-spacing': 0,
  // Relax stylistic rules per request
  'no-var': 'off',
  'object-shorthand': 'off',
  'space-before-function-paren': 'off',
  'semi': 'off',
  'key-spacing': 'off',
  'multiline-ternary': 'off',
  'quotes': 'off',
  'no-mixed-spaces-and-tabs': 'off',
  'no-unused-vars': 'warn',
  'quote-props': 'off',
  'no-multiple-empty-lines': 'off',
  'curly': 'warn',
  'import/no-duplicates': 'off',
    quotes: ['error', 'single', { allowTemplateLiterals: true }],
  'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'off',
  // Allow console during migration; switch back later if needed
  'no-console': 'off',

    'vue/require-default-prop': 0,
    'vue/multi-word-component-names': 0,
    'vue/no-v-html': 0,
    'vue/max-attributes-per-line': 0,
  'vue/attribute-hyphenation': ['warn', 'never'],
    'vue/v-on-event-hyphenation': ['warn', 'never'],
    'vue/require-v-for-key': 'warn',
    'vue/valid-v-for': 'warn',
    'vue/no-reserved-keys': 0,
  // Purely stylistic: order of options does not affect Vue runtime behavior
  'vue/order-in-components': 'off',
  'vue/component-definition-name-casing': 'off',

  'camelcase': 0,
  // Allow snake_case identifiers (API payloads, server events)
  'babel/camelcase': 'off',
    'no-unused-expressions': 0,
    'babel/no-unused-expressions': 1,

  indent: 'off',
  'no-trailing-spaces': 'off',
  'eol-last': 'off',
  'prefer-const': 'off'
  }
}

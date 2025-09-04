import pluginVue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import babelParser from '@babel/eslint-parser'

export default [
  // Ignore node_modules and dist
  {
    ignores: ['node_modules/**', 'dist/**', 'build/**', '*.log']
  },
  
  // Base Vue 3 recommended configuration
  ...pluginVue.configs['flat/recommended'],
  
  // Override with custom configuration
  {
    files: ['**/*.js', '**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: babelParser,
        requireConfigFile: false,
        ecmaVersion: 'latest',
        sourceType: 'module',
        babelOptions: {
          babelrc: false,
          configFile: false
        }
      },
      globals: {
        // Node.js globals
        process: 'readonly',
        Buffer: 'readonly',
        global: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
        module: 'readonly',
        require: 'readonly',
        exports: 'readonly',
        
        // Browser globals
        window: 'readonly',
        document: 'readonly',
        navigator: 'readonly',
        console: 'readonly',
        
        // Custom globals from your original config
        localStorage: false,
        $: 'readonly',
        $$: 'readonly'
      }
    },
    rules: {
      // Your custom rules (exactly as they were)
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
      'space-infix-ops': 'off',
      'key-spacing': 'off',
      'multiline-ternary': 'off',
      'quotes': 'off',
      'no-mixed-spaces-and-tabs': 'off',
      'no-unused-vars': 'off',
      'quote-props': 'off',
      'no-multiple-empty-lines': 'off',
      'curly': 'off',
      'import/no-duplicates': 'off',
      
      'quotes': ['error', 'single', { allowTemplateLiterals: true }],
      'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'off',
      
      // Allow console during migration; switch back later if needed
      'no-console': 'off',

      // Vue-specific rules
      'vue/require-default-prop': 0,
      'vue/multi-word-component-names': 0,
      'vue/no-v-html': 0,
      'vue/max-attributes-per-line': 0,
      'vue/attribute-hyphenation': ['warn', 'never'],
      'vue/require-slots-as-functions': 'off',
      'vue/v-on-event-hyphenation': ['warn', 'never'],
      'vue/require-v-for-key': 'warn',
      'vue/valid-v-for': 'warn',
      'vue/no-reserved-keys': 0,
      
      // Purely stylistic: order of options does not affect Vue runtime behavior
      'vue/order-in-components': 'off',
      'vue/component-definition-name-casing': 'off',

      'camelcase': 0,
      'no-unused-expressions': 0,

      'indent': 'off',
      'no-trailing-spaces': 'off',
      'eol-last': 'off',
      'prefer-const': 'off'
    }
  }
]

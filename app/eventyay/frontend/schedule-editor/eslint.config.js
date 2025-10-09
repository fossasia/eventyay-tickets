import vue from 'eslint-plugin-vue'
import vuePug from 'eslint-plugin-vue-pug'
import js from '@eslint/js'
import tseslint from '@typescript-eslint/eslint-plugin'
import tsParser from '@typescript-eslint/parser'

export default [
  // Base JavaScript recommended rules
  js.configs.recommended,
  
  // TypeScript recommended rules for .ts files
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: 'module',
        project: './tsconfig.json'
      }
    },
    plugins: {
      '@typescript-eslint': tseslint
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      // TypeScript-specific rules
      '@typescript-eslint/no-unused-vars': 'warn',
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      '@typescript-eslint/no-non-null-assertion': 'warn',
      '@typescript-eslint/no-empty-object-type': 'warn'
    }
  },
  
  // Vue 3 recommended configuration
  ...vue.configs['flat/recommended'],
  
  // Vue + TypeScript configuration (separate from pure TS to avoid project issues)
  {
    files: ['**/*.vue'],
    languageOptions: {
      parser: vue.parser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: 'module',
        parser: {
          ts: tsParser
        }
        // Removed project reference for Vue files to avoid parsing issues
      }
    },
    plugins: {
      '@typescript-eslint': tseslint
    },
    rules: {
      // Apply some TypeScript rules to Vue files as well
      '@typescript-eslint/no-unused-vars': 'warn',
      '@typescript-eslint/no-explicit-any': 'warn'
    }
  },
  
  // Vue Pug configuration
  {
    plugins: {
      'vue-pug': vuePug
    },
    rules: {
      ...vuePug.configs.recommended.rules
    }
  },
  
  {
    files: ['**/*.js', '**/*.ts', '**/*.vue'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        // Browser globals
        window: 'readonly',
        document: 'readonly',
        console: 'readonly',
        process: 'readonly',
        // Add other browser globals as needed
      }
    },
    
    rules: {
      // Formatting and style rules
      'arrow-parens': 'off',
      'generator-star-spacing': 'off',
      'indent': 'off', // Disable indentation rule due to mixed codebase
      'no-tabs': 'off', // Allow both tabs and spaces
      'comma-dangle': 'off',
      'curly': 'off',
      'no-return-assign': 'off',
      'object-curly-spacing': 'off',
      
      // Override JS no-unused-vars for TypeScript files (handled by @typescript-eslint/no-unused-vars)
      'no-unused-vars': 'off',
      
      // Vue-specific rules
      'vue/require-default-prop': 'off',
      'vue/multi-word-component-names': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/attribute-hyphenation': ['warn', 'never'],
      'vue/v-on-event-hyphenation': ['warn', 'never'],
      'vue/no-v-html': 'off',
      'vue/require-v-for-key': 'warn',
      'vue/valid-v-for': 'warn',
      'vue/component-api-style': ['error', ['composition', 'options', 'script-setup']],
      'vue/no-undef-properties': 'off',
      'vue/require-explicit-emits': 'off',
      'vue/no-mutating-props': 'error',
    }
  }
]

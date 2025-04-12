import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import UnoCSS from 'unocss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // We use vue-scoped mode to avoid conflicts with the CSS from Django app.
    UnoCSS({ mode: 'vue-scoped' }),
  ],
  build: {
    // We don't minify generated code, because it will go through Django compressor.
    minify: false,
    cssMinify: false,
    sourcemap: false,
    rollupOptions: {
      output: {
        // The compiled output should have predictable names, so that we can use them in the Django template.
        // The name of the output file is hardcoded in the Django template.
        entryFileNames: 'js/global-nav-menu.js',
        assetFileNames: "[ext]/global-nav-menu.[name][extname]",
      }
    }
  }
})

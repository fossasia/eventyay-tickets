import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import UnoCSS from 'unocss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [
      vue(),
      // We use vue-scoped mode to avoid conflicts with the CSS from Django app.
      UnoCSS({ mode: 'vue-scoped' }),
    ],
  build: {
    outDir: env.OUT_DIR ? `${env.OUT_DIR}/global-nav-menu` : 'dist',
    emptyOutDir: false,
    manifest: 'pretalx-manifest.json',
    rollupOptions: {
      output: {
        // The compiled output should have predictable names, so that we can use them in the Django template.
        // The name of the output file is hardcoded in the Django template.
        entryFileNames: 'js/global-nav-menu.js',
        assetFileNames: "[ext]/global-nav-menu.[name][extname]",
      }
    }
  }
  }
})

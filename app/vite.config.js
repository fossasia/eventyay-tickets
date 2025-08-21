import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  
  // Build configuration
  build: {
    // Output directory for built assets
    outDir: 'eventyay/exhibitors/static/exhibitors/dist',
    
    // Generate manifest for Django integration
    manifest: true,
    
    // Multiple entry points for different apps
    rollupOptions: {
      input: {
        // Exhibitor app entry point
        main: resolve(__dirname, 'eventyay/exhibitors/static/exhibitors/js/main.js'),
        
        // Add other app entry points as needed
        // main: resolve(__dirname, 'eventyay/static/js/main.js'),
      },
      
      output: {
        // Organize output files
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name.split('.')
          const ext = info[info.length - 1]
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(ext)) {
            return `images/[name]-[hash][extname]`
          }
          if (/css/i.test(ext)) {
            return `css/[name]-[hash][extname]`
          }
          return `assets/[name][extname]`
        }
      }
    },
    
    // Enable source maps for development
    sourcemap: true,
    
    // Minify in production
    minify: 'terser',
    
    // Target modern browsers
    target: 'es2015',
    
    emptyOutDir: true
  },
  
  // Development server configuration
  server: {
    host: '127.0.0.1',
    port: 3000,
    
    // Proxy API requests to Django during development
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false
      },
      '/admin': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false
      }
    }
  },
  
  // Resolve configuration
  resolve: {
    alias: {
      '@': resolve(__dirname, 'eventyay'),
      '@exhibitors': resolve(__dirname, 'eventyay/exhibitors/static/exhibitors'),
      '@components': resolve(__dirname, 'eventyay/exhibitors/static/exhibitors/js/components'),
      '@views': resolve(__dirname, 'eventyay/exhibitors/static/exhibitors/js/views'),
      '@store': resolve(__dirname, 'eventyay/exhibitors/static/exhibitors/js/store')
    },
    
    extensions: ['.js', '.vue', '.json', '.ts']
  },
  
  // CSS configuration
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@import "@/static/scss/variables.scss";`
      }
    }
  },
  
  // Define global constants
  define: {
    __VUE_OPTIONS_API__: true,
    __VUE_PROD_DEVTOOLS__: false
  }
})
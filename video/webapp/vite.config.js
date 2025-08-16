import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import visualizer from 'rollup-plugin-visualizer'
import path from 'path'
import inject from '@rollup/plugin-inject'
import commonjs from '@rollup/plugin-commonjs'
import BuntpapierStylus from 'buntpapier/stylus.js'
import eslint from 'vite-plugin-eslint'

const stylusOptions = {
  paths: [
    path.resolve(__dirname, './src/styles'),
    'node_modules'
  ],
  use: [BuntpapierStylus({ implicit: false })],
  imports: [
    'buntpapier/buntpapier/index.styl',
    path.resolve(__dirname, 'src/styles/variables.styl'),
    path.resolve(__dirname, 'src/styles/themed-buntpapier.styl'),
  ]
}

export default defineConfig(({ mode }) => {
  const currentYear = new Date().getFullYear()
  
  return {
    base: '/video',
    server: {
      host: '0.0.0.0',
      port: 8880,
      hmr: {
        host: 'wikimedia.eventyay.com',
        port: 8880
      },
      allowedHosts: [
        '.localhost',
        '.eventyay.com',
        'app-test.eventyay.com',
        'app.eventyay.com',
        'wikimedia.eventyay.com'
      ]
    },
    plugins: [
      vue(),
      // Enable PWA in production builds by default (parity with vue-cli PWA)
      mode === 'production' && VitePWA({
        registerType: 'autoUpdate',
        manifest: {
          name: 'eventyay',
          theme_color: '#180044',
          icons: [
            {
              src: '/video/eventyay-logo.192.png',
              type: 'image/png',
              sizes: '192x192'
            },
            {
              src: '/video/eventyay-logo.512.png',
              type: 'image/png',
              sizes: '512x512'
            },
            {
              src: '/video/eventyay-logo.svg',
              sizes: '192x192',
              type: 'image/svg+xml'
            },
            {
              src: '/video/eventyay-logo.svg',
              sizes: '512x512',
              type: 'image/svg+xml'
            }
          ]
        },
        // Avoid precaching index.html (parity with previous Workbox exclude)
        workbox: {
          skipWaiting: true,
          clientsClaim: true,
          // Only precache static assets; exclude HTML documents
          globPatterns: ['**/*.{js,css,ico,png,svg}'],
          // Allow larger assets (default is ~2MB); needed for 2.5MB PNG
          maximumFileSizeToCacheInBytes: 3 * 1024 * 1024
        }
      }),
      // Added ESLint plugin to support lintOnSave functionality
      eslint({
        include: ['src/**/*.js', 'src/**/*.vue'],
        cache: false
      }),
  // Modernizr removed; using native feature checks in preloader instead
      mode === 'production' && process.env.ANALYZE && visualizer({
        open: true,
        filename: 'dist/bundle-report.html'
      })
    ].filter(Boolean),
    css: {
      preprocessorOptions: {
        stylus: stylusOptions,
        styl: stylusOptions
      }
    },
    resolve: {
      extensions: ['.js', '.json', '.vue'],
      preserveSymlinks: true,
      alias: {
        'App': path.resolve(__dirname, 'src/App.vue'),
        '~': path.resolve(__dirname, 'src'),
        config: path.resolve(__dirname, 'config.js'),
        react: 'preact/compat',
        'react-dom': 'preact/compat',
        // Some legacy bundles or sourcemaps may reference this deep path; normalize to supported entry
        'preact/hooks/dist/hooks.js': 'preact/hooks',
        // Use official entrypoints; avoid deep paths that may not exist across versions
        assets: path.resolve(__dirname, 'src/assets'),
        components: path.resolve(__dirname, 'src/components'),
        lib: path.resolve(__dirname, 'src/lib'),
        locales: path.resolve(__dirname, 'src/locales'),
        router: path.resolve(__dirname, 'src/router'),
        store: path.resolve(__dirname, 'src/store'),
        styles: path.resolve(__dirname, 'src/styles'),
        views: path.resolve(__dirname, 'src/views'),
        features: path.resolve(__dirname, 'src/features'),
        i18n: path.resolve(__dirname, 'src/i18n'),
        theme: path.resolve(__dirname, 'src/theme'),
        'has-emoji': path.resolve(__dirname, 'build/has-emoji/emoji.json'),
        // Reduce moment-timezone data size similar to previous webpack plugin
        'moment-timezone': 'moment-timezone/builds/moment-timezone-with-data-10-year-range'
      }
    },
    optimizeDeps: {
      exclude: [
        'buntpapier', 
        'color', 
        'pdfjs-dist',
        '@pretalx/schedule'
      ],
      esbuildOptions: {
        target: 'esnext'
      }
    },
    build: {
      target: 'esnext',
  chunkSizeWarningLimit: 2500,
      rollupOptions: {
        input: {
          main: path.resolve(__dirname, 'index.html'),
          preloader: path.resolve(__dirname, 'src/preloader.js')
        },
        output: {
          entryFileNames: (chunkInfo) => {
            return chunkInfo.name === 'preloader' 
              ? '[name].js' 
              : 'assets/[name]-[hash].js'
          }
        },
        plugins: [
          commonjs({
            include: /node_modules\/janus-gateway/,
            requireReturnsDefault: 'auto'
          }),
          inject({
            adapter: ['webrtc-adapter', 'default']
          })
        ]
      }
    },
    define: {
      ENV_DEVELOPMENT: mode === 'development',
      RELEASE: `'${process.env.VENUELESS_COMMIT_SHA}'`,
      BASE_URL: `'${process.env.BASE_URL || '/'}'`,
      'process.env.NODE_PATH': `'${process.env.NODE_PATH}'`,
      __CURRENT_YEAR__: currentYear
    }
  }
})
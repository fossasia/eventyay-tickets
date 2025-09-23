import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import ReactivityTransform from '@vue-macros/reactivity-transform/vite'
import { VitePWA } from 'vite-plugin-pwa'
import visualizer from 'rollup-plugin-visualizer'
import path from 'path'
import commonjs from '@rollup/plugin-commonjs'
import eslint from 'vite-plugin-eslint'

const stylusOptions = {
  paths: [
    path.resolve(__dirname, './src/styles'),
    path.resolve(__dirname, 'node_modules'),
    path.resolve(__dirname, 'node_modules/buntpapier')
  ],
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
      ReactivityTransform(),
      // Enable PWA only in production builds (avoid SW claim issues during dev)
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
        lodash: 'lodash-es',
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
  'moment-timezone': 'moment-timezone/builds/moment-timezone-with-data-10-year-range',
  // Provide default export for 'sdp' to satisfy janus/webrtc-adapter import style
  sdp: path.resolve(__dirname, 'src/shims/sdp-default.js')
      }
    },
    optimizeDeps: {
      include: [
        'color',
        'buntpapier'
      ],
      exclude: [
        'pdfjs-dist',
        '@pretalx/schedule' // excluded pretalx since local components replace its usage
      ],
      esbuildOptions: {
        target: 'esnext'
      }
    },
    build: {
      target: 'esnext',
      sourcemap: true, // Added for debugging vendor-webrtc issue
      chunkSizeWarningLimit: 1250,
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
          },
          // Manual chunking to keep the main app bundle small and
          // isolate large vendor assets.
          manualChunks(id) {
            if (id.includes('node_modules')) {
              // Consolidate WebRTC libs to a single chunk to avoid evaluation order races
              if (id.includes('janus-gateway') || id.includes('webrtc-adapter')) return 'vendor-rtc'
              if (id.includes('materialdesignicons-webfont') || id.match(/materialdesignicons/)) return 'vendor-mdi'
              if (id.includes('pdfjs-dist')) return 'vendor-pdfjs'
              if (id.includes('moment') || id.includes('moment-timezone')) return 'vendor-moment'
              if (id.includes('lodash') || id.includes('lodash-es')) return 'vendor-lodash'
              if (id.includes('quill')) return 'vendor-quill'
              if (id.includes('markdown-it')) return 'vendor-markdown'
              if (id.includes('i18next')) return 'vendor-i18n'
              if (id.includes('buntpapier')) return 'vendor-buntpapier'
              if (id.includes('preact')) return 'vendor-preact'
              if (id.includes('vue') || id.includes('vue-router') || id.includes('vuex') || id.includes('vue-virtual-scroller')) return 'vendor-vue'
              // removed pretalx chunk assignment since library removed from usage
              if (id.includes('emoji-mart') || id.includes('emoji-datasource-twitter') || id.includes('emoji-regex') || id.includes('twemoji-emojis')) return 'vendor-emoji'
              if (id.includes('hls.js')) return 'vendor-hls'
              if (id.includes('core-js')) return 'vendor-corejs'
              if (id.includes('dompurify')) return 'vendor-dompurify'
              if (id.includes('sanitize-html')) return 'vendor-sanitizehtml'
              if (id.includes('js-md5')) return 'vendor-md5'
              if (id.includes('uuid')) return 'vendor-uuid'
              if (id.includes('register-service-worker')) return 'vendor-sw'
              if (id.includes('mux-embed') || id.includes('mux.js')) return 'vendor-mux'
              if (id.includes('qrcode')) return 'vendor-qrcode'
              if (id.includes('random-js')) return 'vendor-randomjs'
              if (id.includes('web-animations-js')) return 'vendor-webanimations'
              return 'vendor'
            }
          }
        },
        plugins: [
          commonjs({
            include: /node_modules\/janus-gateway/,
            requireReturnsDefault: 'auto'
          })
        ]
      }
    },
    define: {
      ENV_DEVELOPMENT: mode === 'development',
      RELEASE: `'${process.env.VENUELESS_COMMIT_SHA}'`,
      BASE_URL: `'${process.env.BASE_URL || '/'}'`,
      global: 'globalThis',
      'process.env.NODE_PATH': `'${process.env.NODE_PATH}'`,
      __CURRENT_YEAR__: currentYear
    }
  }
})
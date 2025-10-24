import path from 'path'
import vue from '@vitejs/plugin-vue'
import gettext from './vite-gettext-plugin'
import BuntpapierStylus from 'buntpapier/stylus.js'

const stylusOptions = {
	paths: [
		// stylus does not allow for dynamic resolves, so we just list all paths here and hope it won't explode
		path.resolve(__dirname, './src/styles'),
		'node_modules'
	],
	use: [BuntpapierStylus({implicit: false})],
	imports: ['buntpapier/buntpapier/index.styl', `${path.resolve(__dirname, './src/styles/variables.styl')}`]
}

export default {
	define: {
    	'process.env': {},
  	},
	base: process.env.BASE_URL || '/',
	plugins: [
		gettext(), vue()
	],
	css: {
		preprocessorOptions: {
			stylus: stylusOptions,
			styl: stylusOptions
		}
	},
	resolve: {
		mainFields: ['browser', 'module', 'jsnext:main', 'jsnext'],
		extensions: ['.js', '.json', '.vue', '.ts', '.tsx'],
		alias: {
			'~': path.resolve(__dirname, './src'),
			'moment-timezone': 'moment-timezone/builds/moment-timezone-with-data-10-year-range.js',
			'@': path.resolve(__dirname, './src')
		}
	},
	build: {
		outDir: process.env.OUT_DIR ? `${process.env.OUT_DIR}/schedule-editor` : 'dist',
		emptyOutDir: false,
		manifest: 'pretalx-manifest.json',
		assetsDir: '',
		rollupOptions: { 
			input: 'src/main.ts',
			output: {
				manualChunks: {
					// Separate Vue and its ecosystem
					vue: ['vue'],
					// Separate moment and moment-timezone
					moment: ['moment-timezone', 'moment'],
					// Separate i18next
					i18n: ['i18next'],
					// Separate UI framework
					buntpapier: ['buntpapier'],
					// Separate schema validation
					zod: ['zod']
				}
			}
		},
		target: 'es2022',
	},
	optimizeDeps: {
		exclude: ['moment']
	},
	server: {
	  port: '8080'
	}
}

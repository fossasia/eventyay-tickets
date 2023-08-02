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
		extensions: ['.js', '.json', '.vue'],
		alias: {'~': path.resolve(__dirname, './src')}
	},
	build: {
		outDir: process.env.OUT_DIR,
		emptyOutDir: false,
		manifest: 'pretalx-manifest.json',
		assetsDir: '',
		rollupOptions: {input: 'src/main.js'},
		target: 'es2022',
	},
	server: {
	  port: '8080'
	}
}

const path = require('path')
const webpack = require('webpack')

module.exports = {
	devServer: {
		host: 'localhost',
		port: 8880
	},
	pwa: {
		name: 'venueless',
		themeColor: '#180044',
		manifestOptions: {
			icons: [{
				src: '/venueless-logo.192.png',
				type: 'image/png',
				sizes: '192x192'
			}, {
				src: '/venueless-logo.512.png',
				type: 'image/png',
				sizes: '512x512'
			}, {
				src: '/venueless-logo.svg',
				sizes: '192x192 512x512'
			}],
		},
		workboxOptions: {
			skipWaiting: true,
			clientsClaim: true
		}
	},
	transpileDependencies: ['buntpapier'],
	configureWebpack: {
		resolve: {
			symlinks: false, // don't flatten symlinks (for npm link)
			modules: [path.resolve('src'), path.resolve('src/styles'), 'node_modules'],
			alias: {
				config: path.resolve(__dirname, 'config.js'),
				react: 'preact/compat/dist/compat.js',
				'react-dom': 'preact/compat/dist/compat.js',
				'preact/hooks': 'preact/hooks/dist/hooks.js'
			}
		},
		plugins: [
			new webpack.DefinePlugin({
				ENV_DEVELOPMENT: process.env.NODE_ENV === 'development',
				RELEASE: `'${process.env.RELEASE}'`
			})
		],
	},
	css: {
		loaderOptions: {
			stylus: {
				use: [require('buntpapier/stylus')({implicit: false})],
				import: ['~buntpapier/buntpapier/index.styl', '~variables']
			}
		}
	},
	lintOnSave: true
}

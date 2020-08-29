const path = require('path')
const webpack = require('webpack')
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin

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
			clientsClaim: true,
			exclude: [
				/index\.html/
			]
		}
	},
	transpileDependencies: ['buntpapier'],
	configureWebpack: {
		resolve: {
			symlinks: false, // don't flatten symlinks (for npm link)
			modules: [path.resolve('src'), path.resolve('src/styles'), 'node_modules'],
			alias: {
				config: path.resolve(__dirname, 'config.js'),
				modernizr$: path.resolve(__dirname, '.modernizrrc'),
				react: 'preact/compat/dist/compat.js',
				'react-dom': 'preact/compat/dist/compat.js',
				'preact/hooks': 'preact/hooks/dist/hooks.js'
			}
		},
		module: {
			rules: [{
				// preloader needs support for old browsers
				test: /src\/preloader\.js$/,
				include: path.resolve(__dirname),
				exclude: /node_modules/,
				use: [{
					loader: 'babel-loader',
					options: {
						babelrc: false,
						presets: [
							'@babel/env'
						],
						plugins: [
							'@babel/plugin-syntax-dynamic-import',
						]
					}
				}]
			}, {
				test: /\.modernizrrc$/,
				loader: 'modernizr-loader',
			}]
		},
		plugins: [
			new webpack.DefinePlugin({
				ENV_DEVELOPMENT: process.env.NODE_ENV === 'development',
				RELEASE: `'${process.env.VENUELESS_COMMIT_SHA}'`
			})
		],
	},
	chainWebpack (config) {
		config.entryPoints.clear()
		config.entry('preloader').add('./src/preloader.js')
		if (config.plugins.has('optimize-css')) {
			config.plugin('optimize-css').tap(([options]) => {
				options.cssnanoOptions.preset[1].calc = false
				return [options]
			})
		}
	},
	css: {
		loaderOptions: {
			stylus: {
				use: [require('buntpapier/stylus')({implicit: false})],
				import: ['~buntpapier/buntpapier/index.styl', '~variables', '~themed-buntpapier']
			}
		}
	},
	lintOnSave: true
}

if (process.env.ANALYZE) {
	console.log('building with bundle analyzer')
	module.exports.configureWebpack.plugins.push(new BundleAnalyzerPlugin({analyzerMode: 'static'}))
}

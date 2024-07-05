const path = require('path')
const webpack = require('webpack')
const MomentTimezoneDataPlugin = require('moment-timezone-data-webpack-plugin')
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin

const currentYear = new Date().getFullYear()

const NODE_PATH = process.env.NODE_PATH

module.exports = {
	devServer: {
		host: '0.0.0.0',
		port: 8880,
		public: 'video-dev.eventyay.com',
		allowedHosts: [
			'.localhost',
			'.eventyay.com',
			'video-dev.eventyay.com',
			'video.eventyay.com'
		  ],
	},
	pwa: {
		name: 'eventyay',
		themeColor: '#180044',
		manifestOptions: {
			icons: [{
				src: '/eventyay-logo.192.png',
				type: 'image/png',
				sizes: '192x192'
			}, {
				src: '/eventyay-logo.512.png',
				type: 'image/png',
				sizes: '512x512'
			}, {
				src: '/eventyay-logo.svg',
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
	transpileDependencies: ['buntpapier', 'color', 'pdfjs-dist'],
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
			}, {
				test: require.resolve('janus-gateway'),
				loader: 'exports-loader',
				options: {
					exports: 'Janus',
				},
			}]
		},
		plugins: [
			new webpack.DefinePlugin({
				ENV_DEVELOPMENT: process.env.NODE_ENV === 'development',
				RELEASE: `'${process.env.VENUELESS_COMMIT_SHA}'`
			}),
			new webpack.ProvidePlugin({
				adapter: ['webrtc-adapter', 'default']
			}),
			// TODO check if we can exclude locales
			// new MomentLocalesPlugin({
			// 	localesToKeep: ['en-us', 'en-ie', ]
			// }),
			new MomentTimezoneDataPlugin({
				startYear: currentYear - 1,
				endYear: currentYear + 1,
				...(NODE_PATH ? { cacheDir: `${NODE_PATH}/.cache/moment-timezone-data-webpack-plugin` } : {})
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
		// remove prefetch plugins because WHY
		config.plugins.delete('prefetch')
		config.plugins.delete('preload')
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

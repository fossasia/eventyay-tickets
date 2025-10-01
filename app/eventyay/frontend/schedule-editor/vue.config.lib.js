const path = require('path')

module.exports = {
	configureWebpack: {
		resolve: {
			symlinks: false, // don't flatten symlinks (for npm link)
			modules: [path.resolve('src'), path.resolve('src/styles'), 'node_modules']
		},
		externals: {
			buntpapier: 'commonjs2 buntpapier',
			moment: 'commonjs2 moment',
			'moment-timezone': 'commonjs2 moment-timezone',
			lodash: 'commonjs2 lodash',
			'markdown-it': 'commonjs2 markdown-it'
		}
	},
	chainWebpack (config) {
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
				import: ['~buntpapier/buntpapier/index.styl', '~variables']
			}
		}
	}
}

module.exports = {
	presets: [
		'@vue/cli-plugin-babel/preset'
	],
	plugins: [
		['@babel/plugin-proposal-optional-chaining', { loose: false }],
		['@babel/plugin-proposal-nullish-coalescing-operator', { loose: false }],
		'@babel/plugin-syntax-dynamic-import'
	]
}

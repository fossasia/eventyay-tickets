module.exports = {
	root: true,
	env: {
		node: true
	},
	extends: [
		'plugin:vue/essential',
		'@vue/standard'
	],
	parserOptions: {
		parser: 'babel-eslint'
	},
	overrides: [
		{
			files: [
				'**/__tests__/*.{j,t}s?(x)',
				'**/tests/unit/**/*.spec.{j,t}s?(x)'
			],
			env: {
				mocha: true
			}
		}
	],
	// add your custom rules here
	rules: {
		'arrow-parens': 0,
		'generator-star-spacing': 0,
		indent: [2, 'tab', {SwitchCase: 1}],
		'no-tabs': 0,
		'comma-dangle': 0,
		curly: 0,
		'no-return-assign': 0,
		'vue/require-default-prop': 0,
		'object-curly-spacing': 0,
	}
}

module.exports = {
	extends: [
		'plugin:vue/vue3-recommended',
		'plugin:vue-pug/vue3-recommended'
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
		'vue/multi-word-component-names': 0,
		'vue/max-attributes-per-line': 0,
		'vue/attribute-hyphenation': ['warn', 'never'],
		'vue/v-on-event-hyphenation': ['warn', 'never'],
		'vue/no-v-html': 0,
		'vue/require-v-for-key': ['warn'],
		'vue/valid-v-for': ['warn'],
	}
}

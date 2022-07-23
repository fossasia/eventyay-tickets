module.exports = {
	extends: [
		// add more generic rulesets here, such as:
		"stylelint-config-standard",
		"stylelint-plugin-stylus/standard",
	],
	rules: {
		"rule-empty-line-before": null,
		"declaration-empty-line-before": null,
		"custom-property-empty-line-before": null,
		"string-quotes": null, // enable this?
		"no-empty-source": null, // don't error on empty style in sfc
		"max-line-length": null,
		"no-descending-specificity": null,
		"color-function-notation": "legacy",
		"no-invalid-position-at-import-rule": null, // interferes with stylus
		"font-family-name-quotes": "always-where-recommended",
		"selector-class-pattern": null, // gets confused by stylus syntax
		"font-family-no-missing-generic-family-keyword": null,
		"declaration-block-no-redundant-longhand-properties": [true, {
			ignoreShorthands: ["grid-template"]
		}],
		"alpha-value-notation": "number", // we can't use percentages because cssnano@4 "optimizes" 40% to 1%
		"stylus/declaration-colon": "always",
		"stylus/media-feature-colon": "always",
		"stylus/indentation": "tab",
		"stylus/selector-list-comma": "always",
		"stylus/selector-list-comma-newline-after": "always-multi-line",
		"stylus/selector-type-no-unknown": [true, {ignoreTypes: [
			"page-training-detail-text-rule-set",
			"page-training-detail-logic-rule-set",
			"iron-pages",
			"view-model-aso-panel"
		]}]
	},
};

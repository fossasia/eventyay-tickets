module.exports = {
	// Locales to generate
	locales: ['en'],
	
	// Disable separators to match existing i18n setup
	keySeparator: false,
	namespaceSeparator: false,
	
	// Input patterns for Vue 3 and JavaScript files
	input: ['src/**/*.{vue,js}'],
	
	// Output path for generated locale files
	output: 'src/locales/$LOCALE.json',
	
	// Sort keys alphabetically for consistent diffs
	sort: true,
	
	// Don't create backup files of old catalogs
	createOldCatalogs: false,
	
	// Don't fail build on warnings
	failOnWarnings: false,
	
	// Verbose output for debugging
	verbose: false,
	
	// Lexer configuration - use JavascriptLexer for both Vue and JS files
	// The JavascriptLexer can handle Vue SFC templates and scripts effectively
	lexers: {
		vue: ['JavascriptLexer'],
		js: ['JavascriptLexer']
	},
	
	// Functions to scan for translation calls
	// Covers Vue 3 Options API ($t), Composition API (t), and direct i18next usage
	defaultValue: function(locale, namespace, key) {
		// Return the key as default value for missing translations
		return key
	},
	
	// Additional transform configuration  
	transform: {
		// Translation functions to look for
		functions: ['$t', 't', 'i18next.t'],
		
		// Additional patterns for Vue template syntax
		extensions: ['.vue', '.js'],
		
		// Keep existing keys that aren't found in source
		keepRemoved: false
	}
}

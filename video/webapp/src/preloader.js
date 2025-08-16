import 'styles/preloader.styl'

const showBrowserBlock = function() {
	document.getElementById('browser-block').style.display = 'block'
	document.body.removeChild(document.getElementById('app'))
}

// test API features without Modernizr (keeps bundlers happy)
;(function() {
	try {
		// Critical ES features
		if (typeof Object.values !== 'function') throw new Error('Object.values missing')
		if (typeof Array.prototype.at !== 'function') throw new Error('Array.prototype.at missing')
		if (typeof Promise === 'undefined') throw new Error('Promise missing')

		// Feature checks we previously had via Modernizr
		const missing = []
		// flexbox
		if (!(window.CSS && CSS.supports && CSS.supports('display', 'flex'))) missing.push('flexbox')
		// fetch
		if (!('fetch' in window)) missing.push('fetch')
		// websockets
		if (!('WebSocket' in window)) missing.push('websockets')
		// webanimations (polyfillable)
		const needsWA = !('animate' in Element.prototype)
		if (needsWA) {
			// load web animations polyfill on demand
			import('web-animations-js')
		}
		// ES6 object/collections
		if (!('Map' in window) || !('Set' in window)) missing.push('es6')

		// If any non-polyfilled critical features are missing, block
		if (missing.some(f => f !== 'webanimations')) {
			throw new Error(`Missing features: ${missing.join(', ')}`)
		}

	// load app
		import('./main')
	} catch (e) {
		// swallow error and show browser block
		showBrowserBlock()
	}
})()

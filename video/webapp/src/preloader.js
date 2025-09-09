import 'styles/preloader.styl'

const showBrowserBlock = function() {
	document.getElementById('browser-block').style.display = 'block'
	document.body.removeChild(document.getElementById('app'))
}

// test syntax & API features
;(function() {
	try {
		// modernizr haz no object.values flag
		if (typeof Object.values !== 'function') {
			throw new Error('Object.values not supported')
		}
		if (typeof Array.prototype.at !== 'function') {
			throw new Error('Array.prototype.at not supported')
		}
		// load app
		import('./main')
	} catch (e) {
		console.error(e)
		showBrowserBlock()
	}
})()

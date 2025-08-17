import 'styles/preloader.styl'

const showBrowserBlock = function() {
	document.getElementById('browser-block').style.display = 'block'
	document.body.removeChild(document.getElementById('app'))
}

// Wait for DOM and load main app
function waitForAppDiv() {
	const appDiv = document.getElementById('app')
	if (appDiv) {
		import('./main').catch(e => {
			console.error('Error loading app:', e)
			appDiv.innerHTML = '<h1>Error loading app: ' + e.message + '</h1>'
		})
	} else {
		setTimeout(waitForAppDiv, 100)
	}
}

// Start when DOM is ready
if (document.readyState === 'loading') {
	document.addEventListener('DOMContentLoaded', waitForAppDiv)
} else {
	waitForAppDiv()
}

// Original compatibility checks (simplified)
;(function() {
	try {
		console.log('[PRELOADER] Starting browser compatibility checks')
		
		// Only check the most basic features
		if (typeof Promise === 'undefined') throw new Error('Promise missing')
		if (!('fetch' in window)) throw new Error('fetch missing')
		
		console.log('[PRELOADER] Basic compatibility checks passed')
	} catch (e) {
		console.error('[PRELOADER] Compatibility check failed:', e)
		showBrowserBlock()
	}
})()

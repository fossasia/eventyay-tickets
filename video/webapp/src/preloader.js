/* eslint no-eval: 0 */
import Modernizr from 'modernizr'
import 'styles/preloader.styl'

const showBrowserBlock = function () {
	document.getElementById('browser-block').style.display = 'block'
	document.body.removeChild(document.getElementById('app'))
}

// test syntax & API features
;(function () {
	try {
		eval('const f=(a)=>a')
		eval('function a(b) {for (let b;;);}')
		eval('class __testfail {}')

		// modernizr haz no object.values flag
		if (typeof Object.values !== 'function') {
			throw new Error()
		}
		for (const feature in Modernizr) {
			if (!Modernizr[feature]) {
				if (feature === 'webanimations') {
					console.info('loading webanimations polyfill')
					// eslint-disable-next-line
					import(/* webpackChunkName: "polyfill-webanimations" */ 'web-animations-js')
				} else {
					throw new Error(`Browser feature missing: ${feature}`)
				}
			}
		}

		// load app
		// eslint-disable-next-line
		import(/* webpackChunkName: "app" */ './main')
	} catch (e) {
		console.error(e)
		showBrowserBlock()
	}
})()

export default {
	install(app) {
		app.directive('dynamic-line-clamp', {
			inserted: function (el) {
				const rect = el.getBoundingClientRect()
				el.style.setProperty('--dynamic-line-clamp', Math.floor(rect.height / (14 * 1.4)))
			}
		})
	}
}

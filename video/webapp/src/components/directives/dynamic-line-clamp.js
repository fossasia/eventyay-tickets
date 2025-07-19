export default {
  install(app) {
    app.directive('dynamic-line-clamp', {
      mounted(el) {
		const rect = el.getBoundingClientRect()
		// set webkit-line-clamp
		el.style.setProperty('--dynamic-line-clamp', Math.floor(rect.height / (14 * 1.4)))
	}
})
}}

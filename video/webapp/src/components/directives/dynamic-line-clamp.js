import Vue from 'vue'

Vue.directive('dynamic-line-clamp', {
	inserted: function (el) {
		const rect = el.getBoundingClientRect()
		// set webkit-line-clamp
		el.style.setProperty('--dynamic-line-clamp', Math.floor(rect.height / (14 * 1.4)))
	}
})

import throttle from 'lodash/throttle'

// TODO check semantics with rupture
const SCALE = {
	xs: 480,
	s: 768,
	m: 992,
	l: 1200,
	xl: 1800,
	hd: Infinity
}

const Plugin = {
	install (Vue) {
		const match = function (value, direction) {
			if (SCALE[value]) value = SCALE[value] + (direction === 'min' ? 1 : 0) + 'px'
			return window.matchMedia(`(${direction}-width: ${value})`).matches
		}
		const proxyHandler = function (direction) {
			return {
				get (target, property, receiver) {
					if (typeof property !== 'symbol' && property !== '_isVue') {
						Vue.set(target, property, match(property, direction))
					}
					return Reflect.get(...arguments)
				}
			}
		}

		const mq = Vue.observable({
			above: new Proxy({}, proxyHandler('min')),
			below: new Proxy({}, proxyHandler('max'))
		})
		const updateMatches = function (object, direction) {
			for (const key of Object.keys(object)) {
				Vue.set(object, key, match(key, direction))
			}
		}
		const throttleResize = throttle(() => {
			updateMatches(mq.above, 'min')
			updateMatches(mq.below, 'max')
		}, 200)

		window.addEventListener('resize', throttleResize)
		Object.defineProperty(Vue.prototype, '$mq', {
			get () {
				return mq
			}
		})
	}
}

export default Plugin

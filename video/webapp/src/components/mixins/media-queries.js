import { reactive } from 'vue'
import { throttle } from 'lodash'

// TODO check semantics with rupture
const SCALE = {
	xs: 480,
	s: 768,
	m: 992,
	l: 1400,
	xl: 1800
}

const Plugin = {
	install(app) {
		const match = function(value, direction) {
			if (SCALE[value]) value = SCALE[value] + (direction === 'min' ? 1 : 0) + 'px'
			return window.matchMedia(`(${direction}-width: ${value})`).matches
		}
		const proxyHandler = function(direction) {
			return {
				get(target, property, ...args) {
					if (typeof property !== 'symbol' && !property.startsWith('__v')) {
						target[property] = match(property, direction)
					}
					return Reflect.get(target, property, ...args)
				}
			}
		}

		const mq = reactive({
			above: new Proxy(reactive({}), proxyHandler('min')),
			below: new Proxy(reactive({}), proxyHandler('max'))
		})
		const updateMatches = function(object, direction) {
			for (const key of Object.keys(object)) {
				object[key] = match(key, direction)
			}
		}
		const throttleResize = throttle(() => {
			updateMatches(mq.above, 'min')
			updateMatches(mq.below, 'max')
		}, 200)

		window.addEventListener('resize', throttleResize)
		Object.defineProperty(app.config.globalProperties, '$mq', { get() { return mq } })
	}
}

export default Plugin

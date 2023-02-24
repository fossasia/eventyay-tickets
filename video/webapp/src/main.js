/* global RELEASE */
import Vue from 'vue'
import Buntpapier from 'buntpapier'
import Vuelidate from 'vuelidate'
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import { v4 as uuid } from 'uuid'
import moment from 'lib/timetravelMoment' // init timetravel before anything else to avoid module loading race conditions
import router from 'router'
import store from 'store'
import LinkIconButton from 'components/link-icon-button'
import Scrollbars from 'components/Scrollbars'
import MediaQueries from 'components/mixins/media-queries'
import 'components/directives/dynamic-line-clamp'
import 'styles/global.styl'
import 'roboto-fontface'
import 'roboto-fontface/css/roboto-condensed/roboto-condensed-fontface.css'
import '@mdi/font/css/materialdesignicons.css'
import 'quill/dist/quill.core.css'
import '@pretalx/schedule/dist/schedule.css'
import 'styles/quill.styl'
import i18n, { init as i18nInit } from 'i18n'
import { emojiPlugin } from 'lib/emoji'
import features from 'features'
import config from 'config'

async function init (token) {
	Vue.config.productionTip = false
	Vue.use(Buntpapier)
	Vue.use(Vuelidate)
	Vue.use(VueVirtualScroller)
	Vue.component('scrollbars', Scrollbars)
	Vue.component('link-icon-button', LinkIconButton)
	Vue.use(MediaQueries)
	Vue.use(emojiPlugin)
	await i18nInit(Vue)
	Vue.prototype.$features = features

	const app = new Vue({
		router,
		store,
		render: h => h('router-view')
	}).$mount('#app')
	window.vapp = app

	store.commit('setUserLocale', i18n.resolvedLanguage)
	store.dispatch('updateUserTimezone', localStorage.userTimezone || moment.tz.guess())

	if (token) {
		localStorage.token = token
		router.replace(router.currentRoute.path)
		store.dispatch('login', {token})
	} else if (localStorage.token) {
		store.dispatch('login', {token: localStorage.token})
	} else {
		console.warn('no token found, login in anonymously')
		let clientId = localStorage.clientId
		if (!clientId) {
			clientId = uuid()
			localStorage.clientId = clientId
		}
		store.dispatch('login', {clientId})
	}
	store.dispatch('connect')

	setTimeout(() => {
		store.commit('updateNow')
		setInterval(() => {
			store.commit('updateNow')
		}, 60000)
	}, 60000 - Date.now() % 60000) // align with full minutes
	setInterval(() => store.dispatch('notifications/pollExternals'), 1000)
	window.__venueless__release = RELEASE

	window.addEventListener('beforeinstallprompt', function (event) {
		console.log('install prompt', event)
	})
}

const token = new URLSearchParams(window.location.hash.substring(1)).get('token')

if (config.externalAuthUrl && !token) {
	window.location = config.externalAuthUrl
} else {
	init(token)
}

// remove all old service workers
navigator.serviceWorker?.getRegistrations().then((registrations) => {
	for (const registration of registrations) {
		console.warn('Removed an old service worker')
		registration.unregister()
	}
})

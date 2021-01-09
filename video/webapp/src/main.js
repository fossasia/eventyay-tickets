/* global RELEASE */
import Vue from 'vue'
import Buntpapier from 'buntpapier'
import Vuelidate from 'vuelidate'
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import { v4 as uuid } from 'uuid'
import 'lib/timetravelMoment' // init timetravel before anything else to avoid module loading race conditions
import router from 'router'
import store from 'store'
import Scrollbars from 'components/Scrollbars'
import MediaQueries from 'components/mixins/media-queries'
import 'styles/global.styl'
import 'roboto-fontface'
import 'roboto-fontface/css/roboto-condensed/roboto-condensed-fontface.css'
import '@mdi/font/css/materialdesignicons.css'
import './registerServiceWorker'
import i18n from './i18n'
import features from 'features'

Vue.config.productionTip = false
Vue.use(Buntpapier)
Vue.use(Vuelidate)
Vue.use(VueVirtualScroller)
Vue.component('scrollbars', Scrollbars)
Vue.use(MediaQueries)
// auth.
// history.replaceState('', document.title, location.pathname + location.search)

Vue.prototype.$features = features
window.vapp = new Vue({
	router,
	store,
	i18n,
	render: h => h('router-view')
}).$mount('#app')

const token = new URLSearchParams(router.currentRoute.hash.substr(1)).get('token')
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

// TODO properly time between minutes
setInterval(() => store.commit('schedule/updateNow'), 30000)

window.__venueless__release = RELEASE

window.addEventListener('beforeinstallprompt', function (event) {
	console.log('install prompt', event)
})

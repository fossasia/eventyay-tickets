import Vue from 'vue'
import Buntpapier from 'buntpapier'
import Vuelidate from 'vuelidate'
import shaka from 'shaka-player'
import muxjs from 'mux.js'
import { v4 as uuid } from 'uuid'
import App from './App.vue'
import router from './router'
import store from './store'
import Scrollbars from 'components/Scrollbars'
import 'styles/global.styl'
import 'roboto-fontface'
import '@mdi/font/css/materialdesignicons.css'

Vue.config.productionTip = false
Vue.use(Buntpapier)
Vue.use(Vuelidate)
Vue.component('scrollbars', Scrollbars)
// auth.
// history.replaceState('', document.title, location.pathname + location.search)

shaka.polyfill.installAll()
window.muxjs = muxjs
if (!shaka.Player.isBrowserSupported()) {
	console.error('Browser not supporting shaka player!')
}

window.vapp = new Vue({
	router,
	store,
	render: h => h(App)
}).$mount('#app')

const token = new URLSearchParams(router.currentRoute.hash.substr(1)).get('token')
if (token) {
	localStorage.token = token
	router.replace(router.currentRoute.path)
	store.dispatch('login', {token})
} else if (localStorage.token) {
	store.dispatch('login', localStorage.token)
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

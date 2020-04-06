import Vue from 'vue'
import Buntpapier from 'buntpapier'
import App from './App.vue'
import router from './router'
import store from './store'
import 'styles/global.styl'
import 'roboto-fontface'
import '@mdi/font/css/materialdesignicons.css'

Vue.config.productionTip = false
Vue.use(Buntpapier)

new Vue({
	router,
	store,
	render: h => h(App)
}).$mount('#app')

store.dispatch('connect')

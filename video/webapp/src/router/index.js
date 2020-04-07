import Vue from 'vue'
import VueRouter from 'vue-router'
import Home from 'views'
import Room from 'views/rooms/item'

Vue.use(VueRouter)

const routes = [{
	path: '/',
	name: 'home',
	component: Home,
}, {
	path: '/rooms/:roomId',
	name: 'room',
	component: Room,
	props: true
}]

const router = new VueRouter({
	mode: 'history',
	base: process.env.BASE_URL,
	routes
})

export default router

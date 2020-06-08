import Vue from 'vue'
import VueRouter from 'vue-router'
import Home from 'views'
import Schedule from 'views/schedule'
import Room from 'views/rooms/item'

Vue.use(VueRouter)

const routes = [{
	path: '/',
	name: 'home',
	component: Home,
}, {
	path: '/schedule',
	name: 'schedule',
	component: Schedule,
}, {
	path: '/rooms/:roomId',
	name: 'room',
	component: Room,
	props: true
}, {
	path: '/admin',
	name: 'admin',
	component: () => import(/* webpackChunkName: "admin" */ 'views/admin'),
}, {
	path: '/admin/users',
	name: 'admin:users',
	component: () => import(/* webpackChunkName: "admin" */ 'views/admin/users'),
}]

const router = new VueRouter({
	mode: 'history',
	base: process.env.BASE_URL,
	routes
})

export default router

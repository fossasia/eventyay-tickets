import Vue from 'vue'
import VueRouter from 'vue-router'
import Schedule from 'views/schedule'
import Room from 'views/rooms/item'
import Channel from 'views/channels/item'
Vue.use(VueRouter)

const routes = [{
	path: '/',
	name: 'home',
	component: Room,
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
	path: '/channels/:channelId',
	name: 'channel',
	component: Channel,
	props: true
}, {
	path: '/admin',
	name: 'admin',
	component: () => import(/* webpackChunkName: "admin" */ 'views/admin'),
}, {
	path: '/admin/users',
	name: 'admin:users',
	component: () => import(/* webpackChunkName: "admin" */ 'views/admin/users'),
}, {
	path: '/admin/rooms',
	name: 'admin:rooms',
	component: () => import(/* webpackChunkName: "admin" */ 'views/admin/rooms'),
}, {
	path: '/admin/rooms/:editRoomId',
	name: 'admin:room',
	component: () => import(/* webpackChunkName: "admin" */ 'views/admin/room'),
	props: true
}, {
	path: '/admin/config',
	name: 'admin:config',
	component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config'),
}]

const router = new VueRouter({
	mode: 'history',
	base: process.env.BASE_URL,
	routes
})

export default router

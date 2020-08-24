import Vue from 'vue'
import VueRouter from 'vue-router'
import Room from 'views/rooms/item'
import Channel from 'views/channels/item'
import Schedule from 'views/schedule'
import Talk from 'views/schedule/talks/item'
import Speaker from 'views/schedule/speakers/item'
import Exhibitor from 'views/exhibitors/item'
import ContactRequests from 'views/contact-requests'
Vue.use(VueRouter)

const routes = [{
	path: '/',
	name: 'home',
	component: Room,
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
	path: '/schedule',
	name: 'schedule',
	component: Schedule,
}, {
	path: '/schedule/talks/:talkId',
	name: 'schedule:talk',
	component: Talk,
	props: true
}, {
	path: '/schedule/speakers/:speakerId',
	name: 'schedule:speaker',
	component: Speaker,
	props: true
}, {
	path: '/exhibitors/:exhibitorId',
	name: 'exhibitor',
	component: Exhibitor,
	props: true
}, {
	path: '/contact-requests',
	name: 'contactRequests',
	component: ContactRequests,
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

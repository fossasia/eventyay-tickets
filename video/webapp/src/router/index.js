import Vue from 'vue'
import VueRouter from 'vue-router'
import App from 'App'
import PresentationMode from 'PresentationMode'
import Room from 'views/rooms/item'
import Channel from 'views/channels/item'
import Schedule from 'views/schedule'
import Talk from 'views/schedule/talks/item'
import Speaker from 'views/schedule/speakers/item'
import Exhibitor from 'views/exhibitors/item'
import ContactRequests from 'views/contact-requests'
import Preferences from 'views/preferences'
Vue.use(VueRouter)

const routes = [{
	path: '/rooms/:roomId/presentation',
	name: 'presentation-mode',
	component: PresentationMode,
}, {
	path: '/',
	component: App,
	children: [{
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
		path: '/preferences',
		name: 'preferences',
		component: Preferences,
	}, {
		path: '/manage-exhibitors',
		name: 'exhibitors',
		component: () => import(/* webpackChunkName: "exhibitors" */ 'views/exhibitor-manager'),
	}, {
		path: '/manage-exhibitors/:exhibitorId',
		name: 'exhibitors:exhibitor',
		component: () => import(/* webpackChunkName: "exhibitors" */ 'views/exhibitor-manager/exhibitor'),
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
		path: '/admin/users/:userId',
		name: 'admin:user',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/user'),
		props: true
	}, {
		path: '/admin/rooms',
		name: 'admin:rooms:index',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/rooms/index'),
	}, {
		path: '/admin/rooms/new',
		name: 'admin:rooms:new',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/rooms/new'),
	}, {
		path: '/admin/rooms/:roomId',
		name: 'admin:rooms:item',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/rooms/item'),
		props: true
	}, {
		path: '/admin/config',
		name: 'admin:config',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config'),
	}]
}]

const router = new VueRouter({
	mode: 'history',
	base: process.env.BASE_URL,
	routes
})

export default router

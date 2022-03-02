import Vue from 'vue'
import VueRouter from 'vue-router'
import App from 'App'
import PresentationMode from 'views/rooms/presentation'
import PresentationModeChat from 'views/rooms/presentation/chat'
import PresentationModePoll from 'views/rooms/presentation/poll'
import PresentationModeQuestion from 'views/rooms/presentation/question'
import RoomHeader from 'views/rooms/RoomHeader'
import Room from 'views/rooms/item'
import RoomManager from 'views/rooms/manage'
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
	children: [{
		path: 'chat',
		name: 'presentation-mode:chat',
		component: PresentationModeChat
	}, {
		path: 'poll',
		name: 'presentation-mode:poll',
		component: PresentationModePoll
	}, {
		path: 'question',
		name: 'presentation-mode:question',
		component: PresentationModeQuestion
	}]
}, {
	path: '/',
	component: App,
	children: [{
		// we can't alias this because vue-router links seem to explode
		// manage view gets linked to room url
		path: '/',
		component: RoomHeader,
		children: [{
			path: '',
			name: 'home',
			component: Room
		}]
	}, {
		path: '/rooms/:roomId',
		component: RoomHeader,
		props: true,
		children: [{
			path: '',
			name: 'room',
			component: Room
		}, {
			path: 'manage',
			name: 'room:manage',
			component: RoomManager
		}]
	}, {
		path: '/channels/:channelId',
		name: 'channel',
		component: Channel,
		props: true
	}, {
		path: '/schedule',
		name: 'schedule',
		component: Schedule
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
		component: Preferences
	}, {
		path: '/posters/:posterId',
		name: 'poster',
		component: () => import(/* webpackChunkName: "posters" */ 'views/posters/item'),
		props: true
	}, {
		path: '/manage-exhibitors',
		name: 'exhibitors',
		component: () => import(/* webpackChunkName: "exhibitors" */ 'views/exhibitor-manager')
	}, {
		path: '/manage-exhibitors/:exhibitorId',
		name: 'exhibitors:exhibitor',
		component: () => import(/* webpackChunkName: "exhibitors" */ 'views/exhibitor-manager/exhibitor'),
		props: true
	}, {
		path: '/manage-posters',
		name: 'posters',
		component: () => import(/* webpackChunkName: "posters" */ 'views/poster-manager')
	}, {
		path: '/manage-posters/create',
		name: 'posters:create-poster',
		component: () => import(/* webpackChunkName: "posters" */ 'views/poster-manager/poster'),
		props: {
			create: true
		}
	}, {
		path: '/manage-posters/:posterId',
		name: 'posters:poster',
		component: () => import(/* webpackChunkName: "posters" */ 'views/poster-manager/poster'),
		props: true
	}, {
		path: '/admin',
		name: 'admin',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin')
	}, {
		path: '/admin/users',
		name: 'admin:users',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/users')
	}, {
		path: '/admin/users/:userId',
		name: 'admin:user',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/user'),
		props: true
	}, {
		path: '/admin/rooms',
		name: 'admin:rooms:index',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/rooms/index')
	}, {
		path: '/admin/rooms/new',
		name: 'admin:rooms:new',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/rooms/new')
	}, {
		path: '/admin/rooms/:roomId',
		name: 'admin:rooms:item',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/rooms/item'),
		props: true
	}, {
		path: '/admin/announcements',
		name: 'admin:announcements',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/announcements'),
		children: [{
			path: ':announcementId',
			name: 'admin:announcements:item',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/announcements/item'),
			props: true
		}]
	}, {
		path: '/admin/config',
		component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config'),
		children: [{
			path: '',
			name: 'admin:config',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config/main')
		}, {
			path: 'schedule',
			name: 'admin:config:schedule',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config/schedule')
		}, {
			path: 'theme',
			name: 'admin:config:theme',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config/theme')
		}, {
			path: 'permissions',
			name: 'admin:config:permissions',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config/permissions')
		}, {
			path: 'token-generator',
			name: 'admin:config:token-generator',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config/token-generator')
		}, {
			path: 'registration',
			name: 'admin:config:registration',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config/registration')
		}, {
			path: 'audit-log',
			name: 'admin:config:audit-log',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config/audit-log')
		}, {
			path: 'reports',
			name: 'admin:config:reports',
			component: () => import(/* webpackChunkName: "admin" */ 'views/admin/config/reports')
		}]
	}]
}]

const router = new VueRouter({
	mode: 'history',
	base: process.env.BASE_URL,
	routes
})

export default router

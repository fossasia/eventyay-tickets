/* global BASE_URL */
import { createRouter, createWebHistory } from 'vue-router'
import App from '~/App'
import RoomHeader from 'views/rooms/RoomHeader'
import Room from 'views/rooms/item'
import RoomManager from 'views/rooms/manage'
import Channel from 'views/channels/item'
import Schedule from '@schedule/components/ScheduleView'
import Talk from '@schedule/components/TalkDetail'
import Speakers from '@schedule/components/SpeakersList'
import Speaker from '@schedule/components/SpeakerDetail'
import PublicStars from '@schedule/components/PublicStars'
import Preferences from 'views/preferences'
import config from 'config'

const routes = [
	{
		path: '/standalone/:roomId',
		name: 'standalone',
		component: () => import('views/standalone'),
		children: [{
			path: 'chat',
			name: 'standalone:chat',
			component: () => import('views/standalone/Chat')
		}, {
			path: 'poll',
			name: 'standalone:poll',
			component: () => import('views/standalone/Poll')
		}, {
			path: 'question',
			name: 'standalone:question',
			component: () => import('views/standalone/Question')
		}, {
			path: 'kiosk',
			name: 'standalone:kiosk',
			component: () => import('views/standalone/kiosk')
		}, {
			path: 'anonymous',
			name: 'standalone:anonymous',
			component: () => import('views/standalone/anonymous')
		}]
	},
	{
		path: '/rooms/:roomId/presentation/:mode',
		redirect(to) {
			return {
				path: `/standalone/${to.params.roomId}/${to.params.mode}`
			}
		}
	},
	{
		path: '/:worldName?',
		component: App,
		props: route => ({ worldName: route.params.worldName ?? '' }),
		children: [
			{
				// In organizer area, default root route to the organizer overview dashboard
				path: '',
				redirect: () => {
					if (window.eventyay?.isOrganizerArea) {
						return { name: 'organizer' }
					}
					return { name: 'about' }
				}
			},
			{
				path: 'about',
				alias: 'info',
				redirect: () => {
					if (window.eventyay?.isOrganizerArea) {
						return { name: 'organizer' }
					}
					return undefined
				},
				component: RoomHeader,
				children: [{
					path: '',
					name: 'about',
					component: Room
				}]
			},
			{
				path: 'rooms/:roomId',
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
			},
			{
				path: 'channels/:channelId',
				name: 'channel',
				component: Channel,
				props: true
			},
			{
				path: 'schedule',
				name: 'schedule',
				component: Schedule
			},
			{
				path: 'schedule/talks/:talkId',
				name: 'schedule:talk',
				component: Talk,
				props: route => ({
					talkId: route.params.talkId,
					baseUrl: window.eventyay?.eventUrl || ''
				})
			},
			{
				path: 'schedule/speakers',
				name: 'schedule:speakers',
				component: Speakers
			},
			{
				path: 'schedule/speakers/:speakerId',
				name: 'schedule:speaker',
				component: Speaker,
				props: true
			},
			{
				path: 'schedule/people/:userCode/stars',
				name: 'schedule:public-stars',
				component: PublicStars,
				props: route => ({
					userCode: route.params.userCode,
					baseUrl: window.eventyay?.eventUrl || ''
				})
			},
			{
				path: 'preferences',
				name: 'preferences',
				component: Preferences
			},
			{
				path: 'event',
				name: 'organizer',
				alias: 'admin',
				component: () => import('views/admin')
			},
			{
				path: 'event/users',
				name: 'admin:users',
				component: () => import('views/admin/users')
			},
			{
				path: 'event/users/:userId',
				name: 'admin:user',
				component: () => import('views/admin/user'),
				props: true
			},
			{
				path: 'event/rooms',
				name: 'admin:rooms:index',
				component: () => import('views/admin/rooms/index')
			},
			{
				path: 'event/rooms/new/:type?',
				name: 'admin:rooms:new',
				component: () => import('views/admin/rooms/new')
			},
			{
				path: 'event/rooms/:roomId',
				name: 'admin:rooms:item',
				component: () => import('views/admin/rooms/item'),
				props: true
			},
			{
				path: 'event/chat',
				name: 'admin:chat:index',
				component: () => import('views/admin/chat/index')
			},
			{
				path: 'event/chat/new',
				name: 'admin:chat:new',
				component: () => import('views/admin/chat/new')
			},
			{
				path: 'event/chat/:roomId',
				name: 'admin:chat:item',
				component: () => import('views/admin/chat/item'),
				props: true
			},
			{
				path: 'event/announcements',
				name: 'admin:announcements',
				component: () => import('views/admin/announcements'),
				children: [{
					path: ':announcementId',
					name: 'admin:announcements:item',
					component: () => import('views/admin/announcements/item'),
					props: true
				}]
			},
			{
				path: 'event/kiosks',
				name: 'admin:kiosks:index',
				component: () => import('views/admin/kiosks/index')
			},
			{
				path: 'event/kiosks/new',
				name: 'admin:kiosks:new',
				component: () => import('views/admin/kiosks/new')
			},
			{
				path: 'event/kiosks/:kioskId',
				name: 'admin:kiosks:item',
				component: () => import('views/admin/kiosks/item'),
				props: true
			},
			{
				path: 'event/config',
				name: 'admin:config',
				component: () => import('views/admin/config/main')
			},
			{
				path: 'event/reports',
				alias: 'event/config/reports',
				name: 'admin:reports',
				component: () => import('views/admin/config/reports')
			},
			{
				path: 'event/logs',
				alias: 'event/config/audit-log',
				name: 'admin:logs',
				component: () => import('views/admin/config/audit-log')
			}
		]
	}
]

import { jwtDecode } from 'jwt-decode'
import store from 'store'
import { hasOrganizerTraits } from 'lib/traitGrants'

const router = createRouter({
	history: createWebHistory(config.basePath),
	routes
})

export function checkRoutePermission(to) {
	if (!store.state.permissions) return true
	if (store.getters.isAdminMode) return true
	const name = typeof to.name === 'string' ? to.name : ''
	const hasPerm = store.getters.hasPermission
	const liveFeatures = Object.assign({
		chat_rooms: false,
		kiosks: false,
		direct_messaging: false,
		announcements: true
	}, store.state.world?.live_features || window.eventyay?.liveFeatures || {})

	if (name === 'admin:config') {
		return hasPerm('world:update') || hasPerm('world:rooms.create.stage') || hasPerm('world:rooms.create.bbb')
	}
	if (name === 'admin:logs') {
		return hasPerm('world:update')
	}
	if (name === 'admin:reports') {
		return hasPerm('world:graphs')
	}
	if (name.startsWith('admin:users') || name === 'admin:user') {
		return hasPerm('world:users.list')
	}
	if (name.startsWith('admin:announcements')) {
		return liveFeatures.announcements !== false && hasPerm('world:announce')
	}
	if (name.startsWith('admin:kiosks')) {
		return liveFeatures.kiosks && hasPerm('world:kiosks.manage')
	}
	if (name.startsWith('admin:chat')) {
		return liveFeatures.chat_rooms && (hasPerm('room:update') || hasPerm('world:rooms.create.chat'))
	}
	if (name.startsWith('admin:rooms') || name === 'room:manage') {
		return hasPerm('room:update') || hasPerm('world:rooms.create.stage') || hasPerm('world:rooms.create.bbb') || hasPerm('world:rooms.create.jitsi')
	}
	if (name === 'channel') {
		return Boolean(liveFeatures.direct_messaging) && hasPerm('world:chat.direct')
	}
	if (name === 'room' && to.params?.roomId) {
		const room = store.state.rooms?.find(r => r.id === to.params.roomId)
		if (room && !liveFeatures.chat_rooms) {
			const isChatRoom = (room.modules?.length === 1 && room.modules[0].type === 'chat.native') ||
				room.modules?.some(module => ['channel.janus', 'channel.zoom', 'channel.jitsi'].includes(module.type))
			if (isChatRoom) return false
		}
	}
	return true
}

router.beforeEach((to, from, next) => {
	const isOrganizerRoute = (typeof to.name === 'string' && (to.name.startsWith('admin') || to.name === 'organizer' || to.name === 'room:manage')) ||
		(typeof to.path === 'string' && (to.path.startsWith('/event') || to.path.includes('/manage')))
	if (isOrganizerRoute) {
		const token = store.state.token || localStorage.getItem('token')
		let tokenTraits = []
		if (token) {
			try {
				tokenTraits = jwtDecode(token)?.traits || []
			} catch (e) {}
		}
		const hasManager = hasOrganizerTraits(tokenTraits)
		const hasStorePerm = store.getters.hasPermission('world:users.list') ||
			store.getters.hasPermission('world:update') ||
			store.getters.hasPermission('world:announce') ||
			store.getters.hasPermission('room:update') ||
			store.getters.hasPermission('room:chat.moderate') ||
			store.getters.hasPermission('room:poll.manage') ||
			store.getters.hasPermission('room:question.moderate') ||
			store.getters.hasPermission('world:kiosks.manage') ||
			store.getters.hasPermission('world:graphs')
		const isPermittedWithoutToken = !token && Boolean(
			window.eventyay?.isOrganizerArea ||
			window.eventyay?.hasOrganiserPermissions
		)
		if (!isPermittedWithoutToken && !hasManager && !hasStorePerm) {
			if (to.params?.roomId) {
				return next({ name: 'room', params: { roomId: to.params.roomId } })
			}
			return next({ name: 'about' })
		}
		if (!checkRoutePermission(to)) {
			return next({ name: 'organizer' })
		}
	} else {
		if (!checkRoutePermission(to)) {
			return next({ name: 'about' })
		}
	}
	next()
})

store.watch(
	state => state.permissions,
	(permissions) => {
		if (permissions && router.currentRoute.value) {
			if (!checkRoutePermission(router.currentRoute.value)) {
				const isOrganizerRoute = typeof router.currentRoute.value.name === 'string' &&
					(router.currentRoute.value.name.startsWith('admin') || router.currentRoute.value.name === 'organizer' || router.currentRoute.value.name === 'room:manage')
				router.replace({ name: isOrganizerRoute ? 'organizer' : 'about' })
			}
		}
	}
)

export default router

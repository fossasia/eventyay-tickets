/* eslint import/first: 0 */
import { createRouter, createWebHistory } from 'vue-router'
import config from 'config'
// Route-level code-splitting via dynamic imports
const RoomHeader = () => import('views/rooms/RoomHeader')
const Room = () => import('views/rooms/item')
const RoomManager = () => import('views/rooms/manage')
const Channel = () => import('views/channels/item')
const Schedule = () => import('views/schedule')
const Talk = () => import('views/schedule/talks/item')
const Session = () => import('views/schedule/sessions')
const Speakers = () => import('views/schedule/speakers')
const Speaker = () => import('views/schedule/speakers/item')
const Exhibitor = () => import('views/exhibitors/item')
const ContactRequests = () => import('views/contact-requests')
const Preferences = () => import('views/preferences')

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
		path: '/:worldName',
		component: { template: '<router-view />' },
		props: true,
		children: [
			{
				// we can't alias this because vue-router links seem to explode
				// manage view gets linked to room url
				path: '',
				component: RoomHeader,
				children: [{
					path: '',
					name: 'home',
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
				props: true
			},
			{
				path: 'sessions',
				name: 'schedule:sessions',
				component: Session,
				props: true
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
				path: 'exhibitors/:exhibitorId',
				name: 'exhibitor',
				component: Exhibitor,
				props: true
			},
			{
				path: 'contact-requests',
				name: 'contactRequests',
				component: ContactRequests,
				props: true
			},
			{
				path: 'preferences',
				name: 'preferences',
				component: Preferences
			},
			{
				path: 'posters/:posterId',
				name: 'poster',
				component: () => import('views/posters/item'),
				props: true
			},
			{
				path: 'manage-exhibitors',
				name: 'exhibitors',
				component: () => import('views/exhibitor-manager')
			},
			{
				path: 'manage-exhibitors/:exhibitorId',
				name: 'exhibitors:exhibitor',
				component: () => import('views/exhibitor-manager/exhibitor'),
				props: true
			},
			{
				path: 'manage-posters',
				name: 'posters',
				component: () => import('views/poster-manager')
			},
			{
				path: 'manage-posters/create',
				name: 'posters:create-poster',
				component: () => import('views/poster-manager/poster'),
				props: {
					create: true
				}
			},
			{
				path: 'manage-posters/:posterId',
				name: 'posters:poster',
				component: () => import('views/poster-manager/poster'),
				props: true
			},
			{
				path: 'admin',
				name: 'admin',
				component: () => import('views/admin')
			},
			{
				path: 'admin/users',
				name: 'admin:users',
				component: () => import('views/admin/users')
			},
			{
				path: 'admin/users/:userId',
				name: 'admin:user',
				component: () => import('views/admin/user'),
				props: true
			},
			{
				path: 'admin/rooms',
				name: 'admin:rooms:index',
				component: () => import('views/admin/rooms/index')
			},
			{
				path: 'admin/rooms/new/:type?',
				name: 'admin:rooms:new',
				component: () => import('views/admin/rooms/new')
			},
			{
				path: 'admin/rooms/:roomId',
				name: 'admin:rooms:item',
				component: () => import('views/admin/rooms/item'),
				props: true
			},
			{
				path: 'admin/announcements',
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
				path: 'admin/kiosks',
				name: 'admin:kiosks:index',
				component: () => import('views/admin/kiosks/index')
			},
			{
				path: 'admin/kiosks/new',
				name: 'admin:kiosks:new',
				component: () => import('views/admin/kiosks/new')
			},
			{
				path: 'admin/kiosks/:kioskId',
				name: 'admin:kiosks:item',
				component: () => import('views/admin/kiosks/item'),
				props: true
			},
			{
				path: 'admin/config',
				component: () => import('views/admin/config'),
				children: [{
					path: '',
					name: 'admin:config',
					component: () => import('views/admin/config/main')
				},
				{
					path: 'schedule',
					name: 'admin:config:schedule',
					component: () => import('views/admin/config/schedule')
				},
				{
					path: 'theme',
					name: 'admin:config:theme',
					component: () => import('views/admin/config/theme')
				},
				{
					path: 'permissions',
					name: 'admin:config:permissions',
					component: () => import('views/admin/config/permissions')
				},
				{
					path: 'token-generator',
					name: 'admin:config:token-generator',
					component: () => import('views/admin/config/token-generator')
				},
				{
					path: 'registration',
					name: 'admin:config:registration',
					component: () => import('views/admin/config/registration')
				},
				{
					path: 'privacy',
					name: 'admin:config:privacy',
					component: () => import('views/admin/config/privacy')
				},
				{
					path: 'audit-log',
					name: 'admin:config:audit-log',
					component: () => import('views/admin/config/audit-log')
				},
				{
					path: 'reports',
					name: 'admin:config:reports',
					component: () => import('views/admin/config/reports')
				}
				]
			}
		]
	},
	{
		path: '/',
		redirect: '/control'
	}
]

const router = createRouter({
	history: createWebHistory(config.basePath),
	routes
})

export default router

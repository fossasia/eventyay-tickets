import Vue from 'vue'
import Vuex from 'vuex'
import i18n from 'i18n'
import jwtDecode from 'jwt-decode'
import api from 'lib/api'
import { doesTraitsMatchGrants } from 'lib/traitGrants'
import announcement from './announcement'
import chat from './chat'
import question from './question'
import poll from './poll'
import roulette from './roulette'
import exhibition from './exhibition'
import schedule from './schedule'
import notifications from './notifications'
import moment from 'lib/timetravelMoment'

Vue.use(Vuex)

export default new Vuex.Store({
	state: {
		token: null,
		clientId: null,
		connected: false,
		socketCloseCode: null,
		fatalConnectionError: null,
		fatalError: null,
		user: null,
		world: null,
		rooms: null,
		roomViewers: null,
		permissions: null,
		activeRoom: null,
		reactions: null,
		mediaSourcePlaceholderRect: null,
		userLocale: null, // only used to force UI render
		userTimezone: null,
		autoplayUserSetting: !localStorage.disableAutoplay ? null : localStorage.disableAutoplay !== 'true',
		stageStreamCollapsed: false,
		now: moment(),
		unblockedIframeDomains: new Set(JSON.parse(localStorage.unblockedIframeDomains || '[]'))
	},
	getters: {
		hasPermission (state) {
			return (permission) => {
				return !!state.permissions?.includes(permission) || (permission.startsWith('room:') && state.activeRoom?.permissions?.includes(permission))
			}
		},
		autoplay (state) {
			if (state.autoplayUserSetting !== null) return state.autoplayUserSetting
			if (!state.token) return true
			const token = jwtDecode(state.token)
			return !doesTraitsMatchGrants(token.traits, state.world.onsite_traits)
		},
		roomsLookup (state) {
			return state.rooms?.reduce((lookup, room) => {
				lookup[room.id] = room
				return lookup
			}, {})
		}
	},
	mutations: {
		updateRooms (state, rooms) {
			// preserve object references for media source
			if (state.rooms) {
				for (const [index, newRoom] of rooms.entries()) {
					const oldRoom = state.rooms.find(r => r.id === newRoom.id)
					if (oldRoom) {
						Object.assign(oldRoom, newRoom) // good enough?
						rooms.splice(index, 1, oldRoom)
					}
				}
			}
			state.rooms = rooms
		},
		reportMediaSourcePlaceholderRect (state, rect) {
			state.mediaSourcePlaceholderRect = rect
		},
		setUserLocale (state, locale) {
			state.userLocale = locale
		},
		updateStageStreamCollapsed (state, stageStreamCollapsed) {
			state.stageStreamCollapsed = stageStreamCollapsed
		},
		updateNow (state) {
			state.now = moment()
		}
	},
	actions: {
		login ({state}, {token, clientId}) {
			state.token = token
			state.clientId = clientId
		},
		connect ({state, dispatch, commit}) {
			api.connect({token: state.token, clientId: state.clientId})
			api.on('joined', (serverState) => {
				state.connected = true
				state.socketCloseCode = null
				state.user = serverState['user.config']
				// state.user.profile = {}
				state.world = serverState['world.config'].world
				state.permissions = serverState['world.config'].permissions
				commit('chat/setJoinedChannels', serverState['chat.channels'])
				commit('chat/setReadPointers', serverState['chat.read_pointers'])
				commit('exhibition/setData', serverState.exhibition)
				commit('announcement/setAnnouncements', serverState.announcements)
				commit('updateRooms', serverState['world.config'].rooms)
				// rejoin room if reconnecting
				if (state.activeRoom) {
					dispatch('changeRoom', state.activeRoom)
				}
				// TODO ?
				// if (!state.user.profile.display_name) {
				// 	router.push('/').catch(() => {}) // force new users to welcome page
				// 	// TODO return after profile update?
				// }
				dispatch('schedule/fetch', {root: true})
			})
			api.on('closed', (code) => {
				state.connected = false
				state.socketCloseCode = code
				dispatch('chat/disconnected', {root: true})
			})
			api.on('error', error => {
				switch (error.code) {
					case 'world.unknown_world':
					case 'auth.invalid_token':
					case 'auth.denied':
					case 'auth.missing_token':
					case 'auth.expired_token':
					case 'auth.missing_id_or_token':
					case 'connection.replaced':
						state.fatalConnectionError = error
						api.close()
						break
					case 'server.fatal':
						state.fatalError = error
						api.close()
						break
				}
				// TODO handle generic fatal error?
			})
		},
		async updateUser ({state, dispatch}, update) {
			await api.call('user.update', update)
			for (const [key, value] of Object.entries(update)) {
				Vue.set(state.user, key, value)
			}
			dispatch('chat/updateUser', {id: state.user.id, update})
		},
		async adminUpdateUser ({dispatch}, update) {
			await api.call('user.admin.update', update)
			const userId = update.id
			delete update.id
			dispatch('chat/updateUser', {id: userId, update})
		},
		async createRoom ({state}, room) {
			return await api.call('room.create', room)
		},
		async changeRoom ({state, dispatch}, room) {
			state.activeRoom = room
			state.reactions = null
			state.roomViewers = null
			if (room?.modules.some(module => ['livestream.native', 'livestream.youtube', 'livestream.iframe', 'call.bigbluebutton', 'call.zoom', 'call.janus'].includes(module.type))) {
				const { viewers } = await api.call('room.enter', {room: room.id})
				state.roomViewers = viewers
			}
			dispatch('question/changeRoom', room)
			dispatch('poll/changeRoom', room)
		},
		async addReaction ({state}, reaction) {
			if (!state.activeRoom || !state.connected) return
			await api.call('room.react', {room: state.activeRoom.id, reaction})
		},
		async updateRoomSchedule ({state}, {room, schedule_data}) {
			return await api.call('room.schedule', {room: room.id, schedule_data})
		},
		async updateUserLocale ({state}, locale) {
			await i18n.changeLanguage(locale)
			state.userLocale = locale
		},
		updateUserTimezone ({state}, timezone) {
			moment.tz.setDefault(timezone)
			state.userTimezone = timezone
			localStorage.userTimezone = timezone // TODO this bakes the auto-detected timezone into localStorage on first load, do we really want this?
		},
		setAutoplay ({state, getters}, autoplay) {
			if (getters.autoplay === autoplay) return
			state.autoplayUserSetting = autoplay
			localStorage.disableAutoplay = !autoplay
		},
		unblockIframeDomain ({state}, domain) {
			state.unblockedIframeDomains.add(domain)
			localStorage.unblockedIframeDomains = JSON.stringify(Array.from(state.unblockedIframeDomains))
			// TODO propagate between tabs?
		},
		'api::room.create' ({state}, room) {
			state.rooms.push(room)
			// TODO ordering?
		},
		'api::room.delete' ({state}, {id}) {
			const index = state.rooms.findIndex(room => room.id === id)
			if (index >= 0) {
				state.rooms.splice(index, 1)
			}
		},
		'api::room.reaction' ({state}, {room, reactions}) {
			if (state.activeRoom.id !== room) return
			state.reactions = reactions
		},
		'api::world.updated' ({state, commit, dispatch}, {world, rooms, permissions}) {
			state.world = world
			state.permission = permissions
			commit('updateRooms', rooms)
		},
		'api::world.schedule.updated' ({state, commit, dispatch}, pretalx) {
			state.world.pretalx = pretalx
			dispatch('schedule/fetch', {root: true})
		},
		'api::world.user_count_change' ({state, commit, dispatch}, {room, users}) {
			room = state.rooms.find(r => r.id === room)
			room.users = users
			commit('updateRooms', state.rooms)
		},
		'api::room.schedule' ({state}, {room, schedule_data}) {
			room = state.rooms.find(r => r.id === room)
			if (!room) return
			Vue.set(room, 'schedule_data', schedule_data)
		},
		'api::user.updated' ({state, dispatch}, update) {
			for (const [key, value] of Object.entries(update)) {
				Vue.set(state.user, key, value)
			}
			dispatch('chat/updateUser', {id: state.user.id, update})
		},
		'api::room.viewer.added' ({state}, {user}) {
			if (!state.roomViewers) return
			// overwrite existing user
			const index = state.roomViewers.findIndex(u => u.id === user.id)
			if (index >= 0) {
				Vue.set(state.roomViewers, index, user)
			} else {
				state.roomViewers.push(user)
			}
		},
		'api::room.viewer.removed' ({state}, {user_id: userId}) {
			if (!state.roomViewers) return
			const index = state.roomViewers.findIndex(u => u.id === userId)
			if (index >= 0) {
				state.roomViewers.splice(index, 1)
			}
		}
	},
	modules: {
		announcement,
		chat,
		question,
		poll,
		exhibition,
		schedule,
		roulette,
		notifications
	}
})

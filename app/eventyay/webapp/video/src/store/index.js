import Vuex from 'vuex'
import { persistLanguage, changeLanguage } from 'i18n'
import { jwtDecode } from 'jwt-decode'
import api, { initApi } from 'lib/api'
import { doesTraitsMatchGrants } from 'lib/traitGrants'
import announcement from './announcement'
import chat from './chat'
import question from './question'
import poll from './poll'
import roulette from './roulette'
import schedule from './schedule'
import notifications from './notifications'
import moment from 'lib/timetravelMoment'
import { normalizeIframeConsentDomain } from 'lib/iframeConsentDomain'
import {
	STREAM_POLL_BASE_DELAY,
	isPermanentStreamPollError,
	nextStreamPollDelay,
	shouldStopAfterTransientErrors,
	streamPollJitter,
	usesHttpStreamFallback,
} from './streamPolling'

export default new Vuex.Store({
	state: {
		token: null,
		clientId: null,
		connected: false,
		socketCloseCode: null,
		fatalConnectionError: null,
		fatalError: null,
		roomFatalErrors: {},
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
		streamPollInterval: null,
		streamVisibilityHandler: null,
		streamPollingErrorCount: 0,
		streamPollingRetryDelay: STREAM_POLL_BASE_DELAY,
		lastKnownStreamId: null,
		now: moment(),
		unblockedIframeDomains: new Set(
			JSON.parse(localStorage.unblockedIframeDomains || '[]')
				.map((d) => normalizeIframeConsentDomain(d))
				.filter(Boolean)
		),
		interpretationStreamsByRoom: {},
		youtubeTranslationsByRoom: {}
	},
	getters: {
		hasPermission(state) {
			return (permission) => {
				return !!state.permissions?.includes(permission) || (permission.startsWith('room:') && state.activeRoom?.permissions?.includes(permission))
			}
		},
		isAdminMode(state) {
			if (Array.isArray(state.user?.traits) && state.user.traits.includes('admin')) return true
			if (typeof window !== 'undefined' && window.eventyay?.hasStaffSession) return true
			if (!state.token) return false
			try {
				const token = jwtDecode(state.token)
				return Array.isArray(token.traits) && token.traits.includes('admin')
			} catch {
				return false
			}
		},
		autoplay(state) {
			if (state.autoplayUserSetting !== null) return state.autoplayUserSetting
			if (!state.token) return true
			const token = jwtDecode(state.token)
			return !doesTraitsMatchGrants(token.traits, state.world.onsite_traits)
		},
		roomsLookup(state) {
			return state.rooms?.reduce((lookup, room) => {
				lookup[room.id] = room
				return lookup
			}, {})
		},
		eventRouting(state) {
			const organizer = state.world?.organizer_slug
			const event = state.world?.slug || state.world?.id
			if (organizer && organizer !== 'default' && event) {
				return { organizer, event }
			}
			if (typeof window !== 'undefined') {
				const pathParts = window.location.pathname.split('/').filter(Boolean)
				if (pathParts.length >= 2) {
					return { organizer: pathParts[0], event: pathParts[1] }
				}
			}
			return { organizer: null, event: null }
		},
	},
	mutations: {
		updateRooms(state, rooms) {
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
		reportMediaSourcePlaceholderRect(state, rect) {
			state.mediaSourcePlaceholderRect = rect
		},
		setUserLocale(state, locale) {
			state.userLocale = locale
		},
		updateStageStreamCollapsed(state, stageStreamCollapsed) {
			state.stageStreamCollapsed = stageStreamCollapsed
		},
		updateNow(state) {
			state.now = moment()
		},
		updateInterpretationAudio(state, {roomId, interpretation}) {
			if (!roomId) return
			state.interpretationStreamsByRoom = {
				...state.interpretationStreamsByRoom,
				[roomId]: interpretation
			}
			state.youtubeTranslationsByRoom = state.interpretationStreamsByRoom
		},
		updateYoutubeTransAudio(state, {roomId, youtubeTranslation}) {
			if (!roomId) return
			state.interpretationStreamsByRoom = {
				...state.interpretationStreamsByRoom,
				[roomId]: youtubeTranslation
			}
			state.youtubeTranslationsByRoom = state.interpretationStreamsByRoom
		},
		setStreamPollInterval(state, streamPollInterval) {
			state.streamPollInterval = streamPollInterval
		},
		resetStreamPollingBackoff(state) {
			state.streamPollingErrorCount = 0
			state.streamPollingRetryDelay = STREAM_POLL_BASE_DELAY
		},
		incrementStreamPollingErrorCount(state) {
			state.streamPollingErrorCount += 1
		},
		setStreamPollingRetryDelay(state, delay) {
			state.streamPollingRetryDelay = delay
		},
		setStreamVisibilityHandler(state, handler) {
			state.streamVisibilityHandler = handler
		},
		setLastKnownStreamId(state, streamId) {
			state.lastKnownStreamId = streamId
		},
		setRoomCurrentStream(state, {roomId, stream}) {
			const room = state.rooms?.find(r => r.id === roomId)
			if (!room) return
			room.currentStream = stream
		},
		setRoomUpcomingStream(state, {roomId, stream, startsAt}) {
			const room = state.rooms?.find(r => r.id === roomId)
			if (!room) return
			room.upcomingStream = stream
			room.upcomingStreamStartsAt = startsAt
		},
		addUnblockedIframeDomain(state, domain) {
			const normalized = normalizeIframeConsentDomain(domain)
			if (!normalized) return
			// Replace the Set so watchers that track the reference see the change.
			state.unblockedIframeDomains = new Set([...state.unblockedIframeDomains, normalized])
		}
	},
	actions: {
		login({state}, {token, clientId, inviteToken}) {
			state.token = token
			state.clientId = clientId
			state.inviteToken = inviteToken
		},
		connect({state, dispatch, commit}) {
			initApi({token: state.token, clientId: state.clientId, inviteToken: state.inviteToken, store: this})
			api.on('joined', async(serverState) => {
				state.connected = true
				state.socketCloseCode = null
				state.fatalConnectionError = null
				state.fatalError = null
				state.user = serverState['user.config']
				// state.user.profile = {}
				state.world = serverState['world.config'].world
				state.permissions = serverState['world.config'].permissions
				commit('chat/setJoinedChannels', serverState['chat.channels'])
				commit('chat/setReadPointers', serverState['chat.read_pointers'])
				commit('chat/setNotificationCounts', serverState['chat.notification_counts'])
				commit('announcement/setAnnouncements', serverState.announcements)
				commit('updateRooms', serverState['world.config'].rooms)
				// TODO ?
				// if (!state.user.profile.display_name) {
				// 	router.push('/').catch(() => {}) // force new users to welcome page
				// 	// TODO return after profile update?
				// }
				dispatch('schedule/fetch', {root: true})
				dispatch('refreshStreamPolling')
			})
			api.on('closed', (code) => {
				state.connected = false
				state.socketCloseCode = code
				dispatch('chat/disconnected', {root: true})
				dispatch('refreshStreamPolling')
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
				case 'server.fatal': {
					const roomId = state.activeRoom?.id ?? null
					const errorWithContext = {...error, roomId}
					state.fatalError = errorWithContext
					if (roomId) {
						state.roomFatalErrors = {
							...state.roomFatalErrors,
							[roomId]: errorWithContext
						}
					}
					break
				}
				}
				// TODO handle generic fatal error?
			})
		},
		async updateUser({state, dispatch}, update) {
			await api.call('user.update', update)
			for (const [key, value] of Object.entries(update)) {
				state.user[key] = value
			}
			dispatch('chat/updateUser', {id: state.user.id, update})
		},
		async setProfileVisibility({state}, showPublicly) {
			const result = await api.call('user.set_publicly_visible', {show_publicly: showPublicly})
			const newValue = (result && typeof result.show_publicly === 'boolean') ? result.show_publicly : showPublicly
			// Use Object.assign so Vue's reactivity proxy tracks the updated key
			state.user = Object.assign({}, state.user, {show_publicly: newValue})
		},
		async fetchCurrentStream({state, getters, commit}, roomId) {
			if (!roomId) return
			const room = state.rooms?.find(r => r.id === roomId)
			if (!room) return

			const { organizer, event } = getters.eventRouting
			if (!organizer || !event) return

			const url = `/api/v1/organizers/${encodeURIComponent(organizer)}/events/${encodeURIComponent(event)}/rooms/${roomId}/streams/current`
			const authHeader = api._config.token
				? `Bearer ${api._config.token}`
				: (api._config.clientId ? `Client ${api._config.clientId}` : null)
			const headers = { Accept: 'application/json' }
			if (authHeader) headers.Authorization = authHeader

			const response = await fetch(url, { headers, credentials: 'include' })
			if (!response.ok && response.status !== 404) {
				const error = new Error(`Failed to fetch current stream: ${response.status}`)
				error.status = response.status
				throw error
			}

			const currentStream = response.status === 404 ? null : await response.json()
			const streamId = currentStream?.id || null
			const previousStreamId = room.currentStream?.id || null
			const previousStreamUrl = room.currentStream?.url || null
			const currentStreamUrl = currentStream?.url || null

			if (previousStreamId !== streamId || previousStreamUrl !== currentStreamUrl) {
				commit('setRoomCurrentStream', { roomId, stream: currentStream })
			}
			if (state.lastKnownStreamId !== streamId) {
				commit('setLastKnownStreamId', streamId)
			}
		},
		refreshStreamPolling({state, dispatch}) {
			if (state.activeRoom?.id) {
				dispatch('startStreamPolling', state.activeRoom.id)
			}
		},
		startStreamPolling({state, commit, dispatch}, roomId) {
			dispatch('stopStreamPolling')

			if (!usesHttpStreamFallback(state.connected)) {
				return
			}

			const scheduleNext = (delay) => {
				commit('setStreamPollInterval', setTimeout(tick, delay))
			}

			const onVisibilityChange = () => {
				if (document.hidden) {
					if (state.streamPollInterval) {
						clearTimeout(state.streamPollInterval)
						commit('setStreamPollInterval', null)
					}
					return
				}
				// tick() exits without rescheduling while the tab is hidden; restart
				// fallback polling when the tab becomes visible again.
				if (!state.connected) {
					scheduleNext(STREAM_POLL_BASE_DELAY)
				}
			}

			const handlePollError = (error) => {
				console.error('Current stream poll failed', {roomId, status: error.status})
				if (isPermanentStreamPollError(error)) {
					dispatch('stopStreamPolling')
					return
				}
				commit('incrementStreamPollingErrorCount')
				if (shouldStopAfterTransientErrors(state.streamPollingErrorCount)) {
					dispatch('stopStreamPolling')
					return
				}
				commit('setStreamPollingRetryDelay', nextStreamPollDelay(state.streamPollingRetryDelay))
				scheduleNext(streamPollJitter(state.streamPollingRetryDelay))
			}

			const tick = async () => {
				if (!state.activeRoom || state.activeRoom.id !== roomId) {
					dispatch('stopStreamPolling')
					return
				}
				
				let shouldFetch = !document.hidden && usesHttpStreamFallback(state.connected);
				
				if (shouldFetch) {
					try {
						await dispatch('fetchCurrentStream', roomId)
						commit('resetStreamPollingBackoff')
						scheduleNext(streamPollJitter(STREAM_POLL_BASE_DELAY))
					} catch (error) {
						handlePollError(error)
					}
				} else {
					scheduleNext(STREAM_POLL_BASE_DELAY)
				}
			}

			commit('setStreamVisibilityHandler', onVisibilityChange)
			document.addEventListener('visibilitychange', onVisibilityChange)
			scheduleNext(streamPollJitter(0))
		},
		stopStreamPolling({state, commit}) {
			if (state.streamPollInterval) {
				clearTimeout(state.streamPollInterval)
				commit('setStreamPollInterval', null)
			}
			if (state.streamVisibilityHandler) {
				document.removeEventListener('visibilitychange', state.streamVisibilityHandler)
				commit('setStreamVisibilityHandler', null)
			}
			commit('resetStreamPollingBackoff')
		},
		async adminUpdateUser({dispatch}, update) {
			await api.call('user.admin.update', update)
			const userId = update.id
			delete update.id
			dispatch('chat/updateUser', {id: userId, update})
		},
		async createRoom({state}, room) {
			return await api.call('room.create', room)
		},
		async changeRoom({state, dispatch}, room) {
			state.activeRoom = room
			state.reactions = null
			state.roomViewers = null
			if (room && state.roomFatalErrors?.[room.id]) {
				// preserve the last fatal error for the room without attempting to reconnect immediately
				return
			}
			if (room) {
				try {
					const { viewers } = await api.call('room.enter', {room: room.id})
					state.roomViewers = viewers || []
					if (state.roomFatalErrors?.[room.id]) {
						const {[room.id]: _removed, ...rest} = state.roomFatalErrors
						state.roomFatalErrors = rest
					}
				} catch {
					// room.enter failures are non-critical, continue with room change
					state.roomViewers = []
				}
			}
			dispatch('question/changeRoom', room)
			dispatch('poll/changeRoom', room)
		},
		async addReaction({state}, reaction) {
			if (!state.activeRoom || !state.connected) return
			await api.call('room.react', {room: state.activeRoom.id, reaction})
		},
		async updateRoomSchedule({state}, {room, schedule_data}) {
			return await api.call('room.schedule', {room: room.id, schedule_data})
		},
		async updateUserLocale({state}, locale) {
			await persistLanguage(locale)
			await changeLanguage(locale)
			state.userLocale = locale
		},
		updateUserTimezone({state}, timezone) {
			moment.tz.setDefault(timezone)
			state.userTimezone = timezone
			localStorage.userTimezone = timezone // TODO this bakes the auto-detected timezone into localStorage on first load, do we really want this?
		},
		setAutoplay({state, getters}, autoplay) {
			if (getters.autoplay === autoplay) return
			state.autoplayUserSetting = autoplay
			localStorage.disableAutoplay = !autoplay
		},
		unblockIframeDomain({state, commit}, domain) {
			commit('addUnblockedIframeDomain', domain)
			localStorage.unblockedIframeDomains = JSON.stringify(Array.from(state.unblockedIframeDomains))
			// TODO propagate between tabs?
		},
		'api::room.create'({state}, room) {
			state.rooms.push(room)
			// TODO ordering?
		},
		'api::room.delete'({state}, {id}) {
			const index = state.rooms.findIndex(room => room.id === id)
			if (index >= 0) {
				state.rooms.splice(index, 1)
			}
		},
		'api::room.reaction'({state}, {room, reactions}) {
			if (state.activeRoom.id !== room) return
			state.reactions = reactions
		},
		'api::world.updated'({state, commit, dispatch}, {world, rooms, permissions}) {
			state.world = world
			state.permissions = permissions
			commit('updateRooms', rooms)
		},
		// Backwards-compat: server emits 'event.updated' with a payload that contains both
		// 'world' and 'event' keys. Mirror the 'world.updated' handling here.
		'api::event.updated'({state, commit, dispatch}, payload) {
			const world = payload.world || payload.event || payload
			const rooms = payload.rooms || []
			const permissions = payload.permissions
			state.world = world
			state.permissions = permissions
			commit('updateRooms', rooms)
		},
		'api::world.schedule.updated'({state, commit, dispatch}, pretalx) {
			state.world.pretalx = pretalx
			dispatch('schedule/fetch', {root: true})
		},
		// Backwards-compat: server emits 'event.schedule.updated' with pretalx config
		'api::event.schedule.updated'({state, commit, dispatch}, pretalx) {
			if (!state.world) state.world = {}
			state.world.pretalx = pretalx
			dispatch('schedule/fetch', {root: true})
		},
		'api::world.user_count_change'({state, commit, dispatch}, {room, users}) {
			const targetRoom = state.rooms?.find(r => String(r.id) === String(room))
			if (targetRoom) {
				targetRoom.users = users
				commit('updateRooms', [...state.rooms])
			}
		},
		// Backwards-compat: server emits 'event.user_count_change'
		'api::event.user_count_change'({state, commit, dispatch}, {room, users}) {
			const targetRoom = state.rooms?.find(r => String(r.id) === String(room))
			if (targetRoom) {
				targetRoom.users = users
				commit('updateRooms', [...state.rooms])
			}
		},
		'api::room.schedule'({state}, {room, schedule_data}) {
			room = state.rooms.find(r => r.id === room)
			if (!room) return
			room.schedule_data = schedule_data
		},
		'api::user.updated'({state, dispatch}, update) {
			// Replace nested objects (e.g. profile/slides) so Vue tracks kiosk setting changes.
			state.user = Object.assign({}, state.user, update)
			dispatch('chat/updateUser', {id: state.user.id, update})
		},
		'api::room.viewer.added'({state}, {user}) {
			if (!state.roomViewers) return
			// overwrite existing user
			const index = state.roomViewers.findIndex(u => u.id === user.id)
			if (index >= 0) {
				state.roomViewers[index] = user
			} else {
				state.roomViewers.push(user)
			}
		},
		'api::room.viewer.removed'({state}, {user_id: userId}) {
			if (!state.roomViewers) return
			const index = state.roomViewers.findIndex(u => u.id === userId)
			if (index >= 0) {
				state.roomViewers.splice(index, 1)
			}
		},
		'api::room.stream.change'({state, commit, dispatch}, {stream, reload}) {
			if (!state.activeRoom) return
			const room = state.rooms.find(r => r.id === state.activeRoom.id)
			if (!room) return
			const streamId = stream?.id || null
			commit('setRoomCurrentStream', { roomId: room.id, stream })
			commit('setLastKnownStreamId', streamId)
			if (reload && usesHttpStreamFallback(state.connected)) {
				dispatch('fetchCurrentStream', room.id).catch(() => {
					// Stream refresh failures are non-critical
				})
			}
		},
		'api::room.stream.will_change'({state, commit}, {stream, starts_at}) {
			if (!state.activeRoom) return
			const room = state.rooms.find(r => r.id === state.activeRoom.id)
			if (!room) return
			commit('setRoomUpcomingStream', {
				roomId: room.id,
				stream,
				startsAt: starts_at
			})
		}
	},
	modules: {
		announcement,
		chat,
		question,
		poll,
		schedule,
		roulette,
		notifications
	}
})
